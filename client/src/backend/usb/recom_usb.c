#include <tusb.h>
#include <device/usbd_pvt.h>

#include "backend/usb/recom_usb.h"
#include "recom_base_device.h"
#include "recom_defs.h"

/*
 * This module provides USB device  and interface descriptor handling.
 * Based on the TinyUSB descriptor and configuration callbacks, it allows the application
 * to register additional interface descriptors at run-time as well as dynamically update
 * certain device descriptor attributes (e.g. serial number).
 * Once the TinyUSB library has been initialized and enumeration has been completed, these
 * functions should not be called anymore.
 */

#define DEV_CONFIG_DESC_MAX_SIZE    (512)
#define ITF_IDX_OFFSET(num_itf)     (num_itf + 3)

static uint8_t num_interfaces = 0;
static uint8_t num_drivers = 0;
static usbd_class_driver_t interface_class_drivers[RECOM_MAX_INTERFACES] = {};

/*
 * String pointer array. The three required strings are set by default, but the application
 * can overwrite them. Additional strings can be added when an interface is registered.
 */
static const char *descriptor_strings[RECOM_MAX_INTERFACES + 3] = {
    [0] = "Redhill Embedded",
    [1] = "RECOM Product",
    [2] = "v0.0.0",
};

/*
 * Windows support: Microsoft OS 2.0 descriptors.
 *
 * libusb on Windows (and so the RECom host tool) needs the WinUSB driver
 * bound to the device. The descriptors below ask Windows 8.1+ to bind
 * WinUSB automatically, without an INF or a manual driver install
 * (https://learn.microsoft.com/windows-hardware/drivers/usbcon/microsoft-os-2-0-descriptors-specification):
 *  - the BOS descriptor carries a platform capability announcing an MS OS
 *    2.0 descriptor set, retrievable with vendor request
 *    REC_MS_OS_20_VENDOR_CODE;
 *  - the set gives every vendor-class interface the WINUSB compatible ID
 *    and a DeviceInterfaceGUIDs registry property (libusb opens WinUSB
 *    devices through that interface GUID).
 * WinUSB binds to interfaces, so RECom always exposes one of its own
 * (see "Built-in control interface" below) -- otherwise a device without
 * application interfaces would have none, and nothing to bind to.
 *
 * Note: Windows caches whether a device (VID/PID/bcdDevice) has MS OS
 * descriptors. A device that was plugged in before it had them keeps being
 * treated as not having them until bcdDevice changes or its
 * HKLM\SYSTEM\CurrentControlSet\Control\usbflags\VVVVPPPPRRRR key is
 * deleted.
 */

#define MS_OS_20_SET_HEADER_LEN     10
#define MS_OS_20_CONFIG_SUBSET_LEN  8
#define MS_OS_20_FUNC_SUBSET_LEN    8
#define MS_OS_20_COMPAT_ID_LEN      20
#define MS_OS_20_REG_PROPERTY_LEN   132
#define MS_OS_20_FUNC_LEN           (MS_OS_20_FUNC_SUBSET_LEN + MS_OS_20_COMPAT_ID_LEN + \
                                     MS_OS_20_REG_PROPERTY_LEN)
#define MS_OS_20_DESC_INDEX         0x07    /* wIndex of the descriptor-set request */
#define MS_OS_20_WINDOWS_VERSION    0x06030000u /* Windows 8.1 */

/* Interface GUID registered for every RECom WinUSB interface. */
#define RECOM_WINUSB_GUID           "{6CCDEE6A-4143-4393-8794-ED239FDA1406}"

static uint8_t ms_os_20_desc[MS_OS_20_SET_HEADER_LEN + MS_OS_20_CONFIG_SUBSET_LEN +
                             RECOM_MAX_INTERFACES * MS_OS_20_FUNC_LEN];
static uint16_t ms_os_20_desc_len;

#define BOS_DESC_LEN    (5 + 7 + 28)
static uint8_t desc_bos[BOS_DESC_LEN];

//--------------------------------------------------------------------+
//--------------------------------------------------------------------+
// Device Descriptor
//--------------------------------------------------------------------+
tusb_desc_device_t device_descriptor =
{
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = 0x0201,

    .bDeviceClass       = TUSB_CLASS_UNSPECIFIED,
    .bDeviceSubClass    = 0,
    .bDeviceProtocol    = 0,
    .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,

    .idVendor           = 0x2E8A,   // Can be changed by application
    .idProduct          = 0x1234,   // Can be changed by application
    .bcdDevice          = 0x0100,

    .iManufacturer      = 0x01,
    .iProduct           = 0x02,
    .iSerialNumber      = 0x03,

    .bNumConfigurations = 0x01
};

//--------------------------------------------------------------------+
// Configuration Descriptor
//--------------------------------------------------------------------+

/* 
 * Device configuration descriptor. This is an array that is initialized with the device's
 * first and required configuration. As interfaces are added on by the application, this
 * configuration will be updated and more entries added on.
 */
static uint8_t desc_configuration[DEV_CONFIG_DESC_MAX_SIZE] = {
    TUD_CONFIG_DESCRIPTOR(
        1,      // Configuration number. This is the first configuration descriptor
        0,      // bNumInterfaces - This will be updated later
        0,      // iConfig
        9,      // wTotalLength - This will be updated later
        0,      // bmAttr
        50     // maxPower (mA/2)
    )
};



//--------------------------------------------------------------------+
// Interface registration
//--------------------------------------------------------------------+

static uint32_t conf_desc_idx = sizeof(tusb_desc_configuration_t);
static uint8_t ep_in_idx = 1, ep_out_idx = 1;
static uint8_t intf_idx = 0;

/*
 * Adds an interface descriptor to the device's configuration descriptor
 */
static bool recom_usb_add_interface_descriptor(const void *itf_desc, uint32_t itf_desc_len)
{
    /* Make sure the new configuration descriptor fits */
    if (conf_desc_idx + itf_desc_len >= sizeof(desc_configuration))
        return false;

    /* 
     * Get pointer to next available location in descriptor array and copy the new
     * interface descriptor to that location.
     */
    uint8_t *desc = &desc_configuration[conf_desc_idx];
    memcpy(desc, itf_desc, itf_desc_len);

    uint32_t itf_desc_consumed = 0;

    /* 
     * Iterate through the interface descriptor and update the fields as neccessary.
     * NOTE: Since this is a flat data structure, we protect agains erroneous descriptor length
     * information by ensuring that we do not consume more bytes than the descriptor is long.
     * We have already checked that the descriptor will fit, so we don't have to do that anymore.
     */
    while ((itf_desc_consumed < itf_desc_len) && (desc[0] > 0)) {
        if (desc[1] == TUSB_DESC_INTERFACE) {
            /* Update the interface number */
            tusb_desc_interface_t *desc_intf = (tusb_desc_interface_t *)desc;
            desc_intf->bInterfaceNumber = intf_idx++;
            desc_intf->iInterface = ITF_IDX_OFFSET(num_interfaces) + 1;
        } else if (desc[1] == TUSB_DESC_ENDPOINT) {
            /* Update the endpoint address */
            tusb_desc_endpoint_t *desc_ep = (tusb_desc_endpoint_t *)desc;
            if ((desc_ep->bEndpointAddress & TUD_EP_IN) == TUD_EP_IN) {
                desc_ep->bEndpointAddress = ep_in_idx++ | TUD_EP_IN;
            } else {
                desc_ep->bEndpointAddress = ep_out_idx++ | TUD_EP_OUT;
            }
        } else if (desc[1] == TUSB_DESC_INTERFACE_ASSOCIATION){
            /* Update the interface number */
            tusb_desc_interface_assoc_t *desc_assoc = (tusb_desc_interface_assoc_t *)desc;
            desc_assoc->bFirstInterface = intf_idx;
        } else if (desc[1] == TUSB_DESC_CS_INTERFACE && desc[2] == CDC_FUNC_DESC_CALL_MANAGEMENT) {
            /* Update the interface number */
            cdc_desc_func_call_management_t *desc_call = (cdc_desc_func_call_management_t *)desc;
            desc_call->bDataInterface = intf_idx - 1;
        } else if (desc[1] == TUSB_DESC_CS_INTERFACE && desc[2] == CDC_FUNC_DESC_UNION) {
            /* Update the interface number */
            cdc_desc_func_union_t *desc_union = (cdc_desc_func_union_t *)desc;
            desc_union->bControlInterface = intf_idx - 1;
            desc_union->bSubordinateInterface = intf_idx;
        } else {
            RECOM_INFO("RECOM USBD: Unknown descriptor type %d\n\r", desc[1]);
        }
        conf_desc_idx += desc[0];   /* Advance index into descriptor array */
        desc += desc[0];            /* Adcance pointer to configuration descriptor */
        itf_desc_consumed += desc[0];   /* Update the nubmer of bytes consumed */
    }

    /* Finally update the config descriptor itself */
    tusb_desc_configuration_t *desc_config = (tusb_desc_configuration_t *)desc_configuration;
    desc_config->wTotalLength = conf_desc_idx;
    desc_config->bNumInterfaces = intf_idx;

    return true;
}

//--------------------------------------------------------------------+
// RECOM USB processing function(s)
//--------------------------------------------------------------------+

static uint8_t data_out[RECOM_CTRL_BUFFER_SIZE];
static uint8_t data_in[RECOM_CTRL_BUFFER_SIZE];

static struct rec_transport_control rec_ctrl = {
    .type = eREC_TRANSPORT_TYPE_USB,
    .max_data_len = RECOM_CTRL_BUFFER_SIZE,
};

static struct rec_message rec_msg;

static bool recom_control_request(uint8_t rhport, const tusb_control_request_t * request, bool dir_is_out)
{
    bool ret;

    rec_msg.cmd = request->bRequest;
    rec_msg.index = request->wIndex;
    rec_msg.value = request->wValue;
    rec_msg.data_len = request->wLength;

    if (dir_is_out) {
        /* OUT transfer means this is a 'write' request */
        rec_msg.buffer = data_out;
        return rec_bdev_process_msg(&rec_ctrl, &rec_msg, false);
    } else {
        /* IN transfer means this is a 'read' request */
        rec_msg.buffer = data_in;
        ret = rec_bdev_process_msg(&rec_ctrl, &rec_msg, true);
        if (ret == true) {
            /* Complete the data stage even when data_len is 0 -- a
             * successful read with nothing to return (e.g. CMD_LOG_READ
             * once the requested offset has caught up to the end of the
             * log) is a valid, ordinary zero-length IN completion, not a
             * reason to skip tud_control_xfer(): without it, TinyUSB
             * never sends anything back and the host's request times out
             * waiting for a response that was never going to arrive. */
            return tud_control_xfer(rhport, request, data_in, rec_msg.data_len);
        }
        return ret;
    }
}

static bool recom_control_in(uint8_t rhport, uint8_t stage, const tusb_control_request_t *request)
{
    if (stage == CONTROL_STAGE_SETUP) {
        return recom_control_request(rhport, request, false);
    }
    return true;
}

static bool recom_control_out(uint8_t rhport, uint8_t stage, const tusb_control_request_t *request)
{
    if (stage == CONTROL_STAGE_SETUP) {
        if (request->wLength == 0) {
            /* 
             * The host is not sending us any data, so we can process the request right away.
             * Since no data is sent, the device is required to respond with a status stage
             * response. This is done by initiating a control transfer without any data.
             */
            return (recom_control_request(rhport, request, true) && 
                    tud_control_xfer(rhport, request, NULL, 0));
        } else if (request->wLength > sizeof(data_out)) {
            /* The host is sending us more data than we can handle. Reject it! */
            return false;
        } else {
            /* 
             * The host is sending us data and since we are in the SETUP stage we need to prepare
             * the endpoint for receiving this data into our data buffer. Once the data has been
             * received (DATA stage completes), we will get called again and then process the 
             * request.
             */
            return tud_control_xfer(rhport, request, data_out, request->wLength);
        }
    } else if (stage == CONTROL_STAGE_DATA) {
        /* 
         * We have received a request with data. Process it.
         * NOTE: That data reception was initiated by the SETUP stage above.
         */
        return recom_control_request(rhport, request, true);
    }
    return true;
}

/* Handle a vendor-defined control request to the device. */
bool recom_usb_vendor_ctrl_xfer_handler(uint8_t rhport, uint8_t stage,
                                   const tusb_control_request_t *request)
{
    if (request->bRequest == REC_MS_OS_20_VENDOR_CODE &&
        request->wIndex == MS_OS_20_DESC_INDEX &&
        (request->bmRequestType_bit.direction & TUSB_DIR_IN)) {
        /* Windows fetching the MS OS 2.0 descriptor set (see desc_bos). */
        if (stage != CONTROL_STAGE_SETUP) {
            return true;
        }
        return tud_control_xfer(rhport, request, ms_os_20_desc, ms_os_20_desc_len);
    }

    if (request->bmRequestType_bit.direction & TUSB_DIR_IN) {
        return recom_control_in(rhport, stage, request);
    } else {
        return recom_control_out(rhport, stage, request);
    }
}

//--------------------------------------------------------------------+
// TinyUSB Callback functions
//--------------------------------------------------------------------+

static void put_le16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t) v;
    p[1] = (uint8_t) (v >> 8);
}

static void put_le32(uint8_t *p, uint32_t v)
{
    put_le16(p, (uint16_t) v);
    put_le16(p + 2, (uint16_t) (v >> 16));
}

/* Writes an ASCII string as UTF-16LE, including a terminating NUL. */
static uint8_t *put_utf16(uint8_t *p, const char *str)
{
    do {
        put_le16(p, (uint16_t) *str);
        p += 2;
    } while (*str++ != '\0');
    return p;
}

/* WINUSB compatible ID + DeviceInterfaceGUIDs property. Returns the end. */
static uint8_t *put_winusb_features(uint8_t *p)
{
    put_le16(&p[0], MS_OS_20_COMPAT_ID_LEN);
    put_le16(&p[2], 0x0003);                /* MS_OS_20_FEATURE_COMPATBLE_ID */
    memset(&p[4], 0, 16);
    memcpy(&p[4], "WINUSB", 6);
    p += MS_OS_20_COMPAT_ID_LEN;

    uint8_t *prop = p;
    put_le16(&prop[0], MS_OS_20_REG_PROPERTY_LEN);
    put_le16(&prop[2], 0x0004);             /* MS_OS_20_FEATURE_REG_PROPERTY */
    put_le16(&prop[4], 0x0007);             /* REG_MULTI_SZ */
    put_le16(&prop[6], 42);                 /* "DeviceInterfaceGUIDs\0" */
    p = put_utf16(&prop[8], "DeviceInterfaceGUIDs");
    put_le16(p, 80);                        /* GUID + two NULs */
    p = put_utf16(p + 2, RECOM_WINUSB_GUID);
    put_le16(p, 0);                         /* REG_MULTI_SZ list terminator */
    return p + 2;
}

/*
 * Builds the MS OS 2.0 descriptor set from the final configuration
 * descriptor: every vendor-class interface gets WinUSB. A device with a
 * single interface is not composite, and Windows then expects the features
 * directly in the set, without configuration/function subsets.
 */
static void build_ms_os_20_desc(void)
{
    const tusb_desc_configuration_t *cfg = (const tusb_desc_configuration_t *) desc_configuration;
    bool const composite = cfg->bNumInterfaces > 1;
    uint8_t *p = ms_os_20_desc + MS_OS_20_SET_HEADER_LEN;
    uint8_t *cfg_subset = NULL;

    if (composite) {
        cfg_subset = p;
        p += MS_OS_20_CONFIG_SUBSET_LEN;
    }

    for (uint16_t off = cfg->bLength; off + 1 < cfg->wTotalLength;
         off += desc_configuration[off]) {
        const uint8_t *d = &desc_configuration[off];
        if (d[0] == 0) {
            break;
        }
        if (d[1] != TUSB_DESC_INTERFACE) {
            continue;
        }
        const tusb_desc_interface_t *itf = (const tusb_desc_interface_t *) d;
        if (itf->bInterfaceClass != TUSB_CLASS_VENDOR_SPECIFIC || itf->bAlternateSetting != 0) {
            continue;
        }
        if (composite) {
            put_le16(&p[0], MS_OS_20_FUNC_SUBSET_LEN);
            put_le16(&p[2], 0x0002);        /* MS_OS_20_SUBSET_HEADER_FUNCTION */
            p[4] = itf->bInterfaceNumber;
            p[5] = 0;
            put_le16(&p[6], MS_OS_20_FUNC_LEN);
            p = put_winusb_features(p + MS_OS_20_FUNC_SUBSET_LEN);
        } else {
            p = put_winusb_features(p);
            break;
        }
    }

    ms_os_20_desc_len = (uint16_t) (p - ms_os_20_desc);

    put_le16(&ms_os_20_desc[0], MS_OS_20_SET_HEADER_LEN);
    put_le16(&ms_os_20_desc[2], 0x0000);    /* MS_OS_20_SET_HEADER_DESCRIPTOR */
    put_le32(&ms_os_20_desc[4], MS_OS_20_WINDOWS_VERSION);
    put_le16(&ms_os_20_desc[8], ms_os_20_desc_len);

    if (cfg_subset) {
        put_le16(&cfg_subset[0], MS_OS_20_CONFIG_SUBSET_LEN);
        put_le16(&cfg_subset[2], 0x0001);   /* MS_OS_20_SUBSET_HEADER_CONFIGURATION */
        cfg_subset[4] = 0;                  /* configuration index, not value */
        cfg_subset[5] = 0;
        put_le16(&cfg_subset[6], (uint16_t) (p - cfg_subset));
    }
}

static void build_bos_desc(void)
{
    static const uint8_t ms_os_20_platform_uuid[16] = {
        /* {D8DD60DF-4589-4CC7-9CD2-659D9E648A9F} */
        0xDF, 0x60, 0xDD, 0xD8, 0x89, 0x45, 0xC7, 0x4C,
        0x9C, 0xD2, 0x65, 0x9D, 0x9E, 0x64, 0x8A, 0x9F,
    };
    uint8_t *p = desc_bos;

    build_ms_os_20_desc();

    /* BOS header */
    p[0] = 5;
    p[1] = TUSB_DESC_BOS;
    put_le16(&p[2], BOS_DESC_LEN);
    p[4] = 2;                               /* bNumDeviceCaps */
    p += 5;

    /* USB 2.0 Extension: LPM supported */
    p[0] = 7;
    p[1] = TUSB_DESC_DEVICE_CAPABILITY;
    p[2] = 0x02;
    put_le32(&p[3], 0x00000002);
    p += 7;

    /* Platform capability: MS OS 2.0 */
    p[0] = 28;
    p[1] = TUSB_DESC_DEVICE_CAPABILITY;
    p[2] = 0x05;                            /* PLATFORM */
    p[3] = 0;
    memcpy(&p[4], ms_os_20_platform_uuid, 16);
    put_le32(&p[20], MS_OS_20_WINDOWS_VERSION);
    put_le16(&p[24], ms_os_20_desc_len);
    p[26] = REC_MS_OS_20_VENDOR_CODE;
    p[27] = 0;                              /* no alternate enumeration */
}

/*
 * This TinyUSB callback function is invoked when the GET_DEVICE_DESCRIPTOR request
 * is received from the host and returns a pointer to the device descriptor.
 * The device descriptor must exist long enough until transfer completes (i.e. data is
 * passed by reference for DMA transaction and not by copy).
 */
uint8_t const * tud_descriptor_device_cb(void)
{
    return (uint8_t const *) &device_descriptor;
}

/*
 * This TinyUSB callback function is invoked when the GET_CONFIGURATION_DESCRIPTOR request
 * is received from the host and returns a pointer to configuration descriptor.
 * The configuration descriptor must exist long enough until transfer completes (i.e. data is
 * passed by reference for DMA transaction and not by copy).
 */
uint8_t const * tud_descriptor_configuration_cb(uint8_t index)
{
  (void) index; // for multiple configurations
  return desc_configuration;
}

/*
 * This TinyUSB callback is invoked when the GET_STRING_DESCRIPTOR request is recevied from
 * the host and returns a pointer to a correctly formated string descriptor.
 * The string descriptor must exist long enough until transfer completes (i.e. data is
 * passed by reference for DMA transaction and not by copy).
 */
const uint16_t *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    (void) langid;

    RECOM_INFO("RECOM USBD: Get string CB!\n\r");

    static uint16_t str_desc[32];

    uint8_t chr_count;

    if (index >= (RECOM_MAX_INTERFACES + 3)) {
        return NULL;
    } else if (index == 0) {
        /* Language string is hardcoded to English only for now */
        str_desc[1] = 0x0409;
        chr_count = 1;
    } else {
        /* 
         * Note: the 0xEE index string is a Microsoft OS 1.0 Descriptors.
         * https://docs.microsoft.com/en-us/windows-hardware/drivers/usbcon/microsoft-defined-usb-descriptors
         */
        const char* str = descriptor_strings[index - 1];

        /* Cap at maximum string length */
        chr_count = (uint8_t) strlen(str);
        if (chr_count > 31) {
            chr_count = 31;
        }

        /* Convert ASCII string into UTF-16 */
        for(uint8_t i=0; i<chr_count; i++) {
            str_desc[1+i] = str[i];
        }
    }

    /*
     * Now fill in the descriptor header
     * First byte is length (including header), second byte is string type
     */
    str_desc[0] = (uint16_t) ((TUSB_DESC_STRING << 8 ) | (2*chr_count + 2));

    return str_desc;
}

/* 
 * This TinyUSB callback is invoked when a vendor type control transfer occured (on endpoint 0).
 * The request is processed further and then passed on to either the device or interface/class
 * handler.
 * Returning false will stall the control endpoint (e.g. unsupported request)
 */
bool tud_vendor_control_xfer_cb(uint8_t rhport, uint8_t stage,
                                const tusb_control_request_t *request)
{
    switch (request->bmRequestType_bit.recipient) {
    case TUSB_REQ_RCPT_DEVICE:
        /* Device control request */
        return recom_usb_vendor_ctrl_xfer_handler(rhport, stage, request);
    case TUSB_REQ_RCPT_INTERFACE:
        /* Interface control request. Call the registered class' handler */
        if (request->wIndex >= RECOM_MAX_INTERFACES ||
            !interface_class_drivers[request->wIndex].control_xfer_cb) {
            /* Out of bounds or no driver registered */
            return false;
        }
        const usbd_class_driver_t *drv = &interface_class_drivers[request->wIndex];
        if (!drv->control_xfer_cb) {
            /* The driver doesn't have a control transfer handler */
            return false;
        }
        return drv->control_xfer_cb(rhport, stage, request);
    case TUSB_REQ_RCPT_ENDPOINT:
        return false;
    }
    return false;
}

const usbd_class_driver_t *usbd_app_driver_get_cb(uint8_t *countp)
{
    RECOM_INFO("RECOM USBD: Get driver CB!\n\r");
    *countp = num_drivers;
    return (const usbd_class_driver_t *) interface_class_drivers;
}

const uint8_t *tud_descriptor_bos_cb(void)
{
    /* Built on request: the configuration (and so the set of interfaces
     * that need WinUSB) is final once the host enumerates. */
    build_bos_desc();
    return desc_bos;
}

//--------------------------------------------------------------------+
// Application interface
//--------------------------------------------------------------------+

/*
 * Built-in control interface.
 *
 * RECom's own requests go to the device (endpoint 0), so they need no
 * interface -- but Windows binds its WinUSB driver to interfaces, and a
 * RECom device with no application interfaces would otherwise have none.
 * This endpoint-less vendor interface is always interface 0: it is what
 * WinUSB (and so libusb on Windows) attaches to. Vendor requests addressed
 * to it are handled exactly like device requests. It has no endpoints, so
 * host-side scans for RECom data interfaces don't pick it up.
 */
static uint16_t recom_ctrl_itf_open(uint8_t rhport, const tusb_desc_interface_t *itf_desc,
                                    uint16_t max_len)
{
    (void) rhport;
    if (itf_desc->bInterfaceClass != TUSB_CLASS_VENDOR_SPECIFIC ||
        itf_desc->bInterfaceSubClass != REC_CTRL_ITF_SUBCLASS ||
        itf_desc->bInterfaceProtocol != REC_CTRL_ITF_PROTOCOL ||
        itf_desc->bNumEndpoints != 0 || max_len < sizeof(tusb_desc_interface_t)) {
        return 0;
    }
    return sizeof(tusb_desc_interface_t);
}

static bool recom_ctrl_itf_control_xfer(uint8_t rhport, uint8_t stage,
                                        const tusb_control_request_t *request)
{
    if (request->bmRequestType_bit.type != TUSB_REQ_TYPE_VENDOR) {
        return false;
    }
    return recom_usb_vendor_ctrl_xfer_handler(rhport, stage, request);
}

static void recom_ctrl_itf_init(void)
{
}

static void recom_ctrl_itf_reset(uint8_t rhport)
{
    (void) rhport;
}

static bool recom_ctrl_itf_xfer(uint8_t rhport, uint8_t ep_addr, xfer_result_t result,
                                uint32_t xferred_bytes)
{
    (void) rhport;
    (void) ep_addr;
    (void) result;
    (void) xferred_bytes;
    return false;
}

static usbd_class_driver_t recom_ctrl_itf_drv = {
    .name            = "RECOM_CTRL",
    .init            = recom_ctrl_itf_init,
    .reset           = recom_ctrl_itf_reset,
    .open            = recom_ctrl_itf_open,
    .control_xfer_cb = recom_ctrl_itf_control_xfer,
    .xfer_cb         = recom_ctrl_itf_xfer,
    .sof             = NULL,
};

static const tusb_desc_interface_t recom_ctrl_itf_desc = {
    .bLength            = sizeof(tusb_desc_interface_t),
    .bDescriptorType    = TUSB_DESC_INTERFACE,
    .bInterfaceNumber   = 0,
    .bAlternateSetting  = 0,
    .bNumEndpoints      = 0,
    .bInterfaceClass    = TUSB_CLASS_VENDOR_SPECIFIC,
    .bInterfaceSubClass = REC_CTRL_ITF_SUBCLASS,
    .bInterfaceProtocol = REC_CTRL_ITF_PROTOCOL,
    .iInterface         = 0,
};

static bool ctrl_itf_added;

/* Adds the built-in control interface if it isn't there yet. It must be
 * the first interface registered (interface 0, driver 0), whether the
 * application registers its own interfaces before or after recom_init(). */
static bool recom_usb_add_ctrl_itf(void)
{
    if (ctrl_itf_added) {
        return true;
    }
    ctrl_itf_added = true;
    return recom_usb_add_interface(&recom_ctrl_itf_drv, &recom_ctrl_itf_desc,
                                   sizeof(recom_ctrl_itf_desc), "RECom");
}

bool recom_usb_init(struct rec_config *cfg)
{
    if (!recom_usb_add_ctrl_itf()) {
        return false;
    }

    device_descriptor.idVendor = cfg->vendor_id;
    device_descriptor.idProduct = cfg->product_id;
    descriptor_strings[0] = cfg->vendor_str;
    descriptor_strings[1] = cfg->product_str;
    descriptor_strings[2] = cfg->serial_str;
    tusb_init();
    return true;
}

bool recom_usb_task(void)
{
    /* Process pending USB events without blocking. tud_task() is
     * tud_task_ext(UINT32_MAX, false): with an RTOS OSAL that honours the
     * timeout it waits indefinitely for the next event, so a caller that
     * polls recom_task() -- e.g. to flush a control transfer's status stage
     * before resetting -- hangs once the host goes quiet. Callers looping
     * on recom_task() should yield between calls. */
    tud_task_ext(0, false);
    return true;
}

/*
 * Application driver/interface registration function
 */
bool recom_usb_add_interface(usbd_class_driver_t* drv,
                              const void *desc, unsigned int desc_len,
                              const char *str)
{
    if (drv != &recom_ctrl_itf_drv && !recom_usb_add_ctrl_itf()) {
        return false;
    }

    if ((num_interfaces + 1) >= RECOM_MAX_INTERFACES) {
        RECOM_INFO("RECOM USBD: Add custom interface: ERROR - Out of bounds\n\r");
        return false;
    }

    /* 
     * Add the descriptor string to the array by storing the pointer to the string.
     * The string itself is not copied. We only keep track of pointers to strings.
     * NOTE: The index for the descriptor string array needs to account for the 3 required
     * strings that are always in the array. Therefore, when adding a new string, 3 needs to
     * be added to the number of interfaces to get to the actual index.
     */
    descriptor_strings[ITF_IDX_OFFSET(num_interfaces)] = str;

    /* 
     * Register driver by copying the class driver to the internal driver array.
     * TinyUSB expects a pointer to a memory section where these vendor drivers reside in a
     * consecutive manner. Therefore we cannot simply track them using pointers, but need to
     * copy them into an internal driver array.
     * If this interface doesn't have a vendor driver (i.e uses an existing TinyUSB driver)
     * and is set to null, then just skip this.
     */
    if (drv != NULL) {
        memcpy(&interface_class_drivers[num_interfaces], drv, sizeof(usbd_class_driver_t));
        num_drivers++;
    }


    /*
     * Attempt to add the interface descriptor.
     */
    if (!recom_usb_add_interface_descriptor(desc, desc_len)) {
        RECOM_INFO("RECOM USBD: Add custom interface: ERROR adding descriptor\n\r");
        return false;
    }

    num_interfaces++;
    return true;
}