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

/* BOS descriptor */
static const uint8_t desc_bos[] = {
    TUD_BOS_DESCRIPTOR(5, 0)
};

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
static bool interface_was_added = false;
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
            printf("Unknown descriptor type %d\n", desc[1]);
        }
        conf_desc_idx += desc[0];   /* Advance index into descriptor array */
        desc += desc[0];            /* Adcance pointer to configuration descriptor */
        itf_desc_consumed += desc[0];   /* Update the nubmer of bytes consumed */
    }

    /* Finally update the config descriptor itself */
    tusb_desc_configuration_t *desc_config = (tusb_desc_configuration_t *)desc_configuration;
    desc_config->wTotalLength = conf_desc_idx;
    desc_config->bNumInterfaces = intf_idx;

    interface_was_added = true;

    return true;
}

//--------------------------------------------------------------------+
// RECOM USB processing function(s)
//--------------------------------------------------------------------+

static uint8_t data_out[64];
static uint8_t data_in[64];

static struct rec_transport_control rec_ctrl = {
    .type = eREC_TRANSPORT_TYPE_USB,
    .max_data_len = 64,
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
        if (ret == true && rec_msg.data_len > 0) {
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
    if (request->bmRequestType_bit.direction & TUSB_DIR_IN) {
        return recom_control_in(rhport, stage, request);
    } else {
        return recom_control_out(rhport, stage, request);
    }
}

//--------------------------------------------------------------------+
// TinyUSB Callback functions
//--------------------------------------------------------------------+

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

    printf("USBD: Get string CB!\n\r");

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
    printf("USBD: Get driver CB!\n\r");
    *countp = num_drivers;
    return (const usbd_class_driver_t *) interface_class_drivers;
}

const uint8_t *tud_descriptor_bos_cb(void)
{
    return desc_bos;
}

//--------------------------------------------------------------------+
// Application interface
//--------------------------------------------------------------------+

bool recom_usb_init(struct rec_config *cfg)
{
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
    tud_task();
    return true;
}

/*
 * Application driver/interface registration function
 */
bool recom_usb_add_interface(usbd_class_driver_t* drv,
                              const void *desc, unsigned int desc_len,
                              const char *str)
{
    if ((num_interfaces + 1) >= RECOM_MAX_INTERFACES) {
        printf("Add custom interface: ERROR - Out of bounds\n\r");
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
        printf("Add custom interface: ERROR adding descriptor\n\r");
        return false;
    }

    num_interfaces++;
    return true;
}