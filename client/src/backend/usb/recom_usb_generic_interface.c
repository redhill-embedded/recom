#include <stdbool.h>
#include <stdint.h>

#ifdef PLATFORM_RP2040
    #include <pico/util/queue.h>
#endif

#include <tusb.h>
#include <device/usbd_pvt.h>

#include "recom_config.h"
#include "recom_defs.h"
#include "backend/usb/recom_usb.h"

#define DEFAULT_EP_OUT  (0x00)
#define DEFAULT_EP_IN   (0x80)

static uint8_t itf_count = 0;

typedef struct rec_usb_itf_desc {
    tusb_desc_interface_t itf;
    tusb_desc_endpoint_t ep_out;
    tusb_desc_endpoint_t ep_in;
} __attribute__((packed)) rec_usb_itf_desc_t;

typedef struct rec_usb_intf {
    uint8_t itf_num;
    uint8_t ep_in;
    uint8_t ep_out;

    /*------------- From this point, data is not cleared by bus reset -------------*/
    // Endpoint Transfer buffer
    CFG_TUSB_MEM_ALIGN uint8_t epout_buf[CFG_TUD_CDC_EP_BUFSIZE];
    CFG_TUSB_MEM_ALIGN uint8_t epin_buf[CFG_TUD_CDC_EP_BUFSIZE];

    /*------------- From this point, data is not cleared by driver init -------------*/
    uint8_t interface_id;
    uint8_t protocol_id;
    uint8_t *rx_buffer;
    uint32_t rx_buffer_size;
    struct rec_itf *parent;
} rec_usb_intf_t;

#define ITF_MEM_RESET_SIZE  offsetof(struct rec_usb_intf, epout_buf)
#define ITF_MEM_INIT_SIZE   offsetof(struct rec_usb_intf, interface_id)

CFG_TUSB_MEM_SECTION static struct rec_usb_intf _recom_usb_itf_arr[RECOM_MAX_INTERFACES];

/*
 * *************************************
 * * Internal endpoint control helpers *
 * *************************************
 */

/* Primes the OUT endpoint for data reception */
static bool prime_out_ep(struct rec_usb_intf *recom_usb_itf)
{
    /*
     * The endpoint needs to be claimed (marked as in use) first.
     * Once data is received on the endpoint, it will automatically
     * be released.
     */
    if (!usbd_edpt_claim(TUD_OPT_RHPORT, recom_usb_itf->ep_out))
        return false;
    return usbd_edpt_xfer(TUD_OPT_RHPORT, recom_usb_itf->ep_out,
                          recom_usb_itf->epout_buf, sizeof(recom_usb_itf->epout_buf));
}

/* Primes the IN endpoint for data transmission */
static bool prime_in_ep(struct rec_usb_intf *recom_usb_itf)
{
    /*
     * The endpoint needs to be claimed (marked as in use) first.
     * Once data is transmitted on the endpoint, it will automatically
     * be released.
     */
    if (!usbd_edpt_claim(TUD_OPT_RHPORT, recom_usb_itf->ep_in))
        return false;
    return usbd_edpt_xfer(TUD_OPT_RHPORT, recom_usb_itf->ep_in,
                          recom_usb_itf->epin_buf, sizeof(recom_usb_itf->epin_buf));
}

/*
 * *****************************
 * * USBD Driver API (TinyUSB) *
 * *****************************
 */

static void recom_usbd_init(void)
{
    RECOM_INFO("RECOM: Generic USBD init\n\r");
    tu_memclr(_recom_usb_itf_arr, ITF_MEM_INIT_SIZE);
}

static void recom_usbd_reset(uint8_t rhport)
{
    (void) rhport;
    
    RECOM_INFO("RECOM: Generic USBD reset\n\r");

    for (uint8_t i=0; i<itf_count; i++) {
        struct rec_usb_intf *p_itf = &_recom_usb_itf_arr[i];
        tu_memclr(p_itf, ITF_MEM_RESET_SIZE);
        /* Perform any other actions (i.e. FIFO clear) here, if needed */

        /* User callback, if present */
        if (p_itf->parent->cb.generic.driver_reset_cb) {
            p_itf->parent->cb.generic.driver_reset_cb(p_itf->itf_num);
        }
    }
}

static uint8_t open_failed = 0;

static uint16_t recom_usbd_open(uint8_t rhport,
                             const tusb_desc_interface_t *itf_desc,
                             __unused uint16_t max_len)
{   
    /* Can only manage vendor interfaces! */
    if (itf_desc->bInterfaceClass != TUSB_CLASS_VENDOR_SPECIFIC) {
        open_failed = 1;
        return 0;
    }

    (void) open_failed;

    /* Find interface that matches the interface and protocol IDs and is available */
    struct rec_usb_intf *p_itf = NULL;
    for (uint8_t i=0; i<itf_count; i++) {
        if (_recom_usb_itf_arr[i].interface_id == itf_desc->bInterfaceSubClass ||
            _recom_usb_itf_arr[i].protocol_id == itf_desc->bInterfaceProtocol)
            if (_recom_usb_itf_arr[i].ep_in == 0) {
                /* Found it! */
                p_itf = &_recom_usb_itf_arr[i];
                break;
        }
    }
    if (p_itf == NULL) {
        open_failed = 2;
        return 0;
    }

    /* Get the control interface number */
    p_itf->itf_num = itf_desc->bInterfaceNumber;

    /* Get pointer to the next descriptor blob, which is the first endpoint descriptor */
    const uint8_t *desc_ep = tu_desc_next(itf_desc);
    if (tu_desc_type(desc_ep) != TUSB_DESC_ENDPOINT) {
        open_failed = 3;
        return 0;
    }

    /* Initialize and open the two endpoints */
    if (usbd_open_edpt_pair(rhport, desc_ep, 2, TUSB_XFER_BULK,
                                  &p_itf->ep_out, &p_itf->ep_in), 0) {
        open_failed = 4;
        return 0;
    }
    RECOM_DEBUG("RECOM: Itf %d, EPOUT=0x%02X, EP_IN=0x%02X\n\r", p_itf->itf_num,
                p_itf->ep_out, p_itf->ep_in);

    /* Prepare the OUT endpoint for reception */
    prime_out_ep(p_itf);

    /* User callback, if present */
    if (p_itf->parent->cb.generic.driver_open_cb) {
        p_itf->parent->cb.generic.driver_open_cb(p_itf->itf_num);
    }

    /* Interface open succeeded. We have consumed the entire interface descriptor */
    const uint16_t drv_len = sizeof(struct rec_usb_itf_desc);
    RECOM_INFO("RECOM: Generic Driver open. Itf=%d\n\r", p_itf->itf_num);
    return drv_len;
}

/*
 * RECOM control interface callback
 */
static bool recom_usbd_control_xfer_cb(__unused uint8_t rhport, uint8_t stage, const tusb_control_request_t *request)
{
    struct rec_usb_intf* p_itf = NULL;
    struct rec_message rec_ctrl_msg;

    /* Identiy which interface to use */
    for (uint8_t i=0; i<itf_count; i++) {
        if (_recom_usb_itf_arr[i].itf_num == request->wIndex) {
            p_itf = &_recom_usb_itf_arr[i];
            break;
        }
    }
    if (p_itf == NULL) {
        RECOM_DEBUG("RECOM USBD: Invalid interface\n\r");
        return false;
    }

    RECOM_DEBUG("RECOM USBD: Control Xfer. Itf=%d\n\r", p_itf->itf_num);

    rec_ctrl_msg.cmd = request->bRequest;
    rec_ctrl_msg.index = request->wIndex;
    rec_ctrl_msg.value = request->wValue;
    rec_ctrl_msg.data_len = request->wLength;

    if (request->bmRequestType_bit.direction & TUSB_DIR_IN) {
        if (stage == CONTROL_STAGE_SETUP) {
            if (p_itf->parent->cb.generic.ctrl_cb != NULL) {
                rec_ctrl_msg.buffer = p_itf->epin_buf;
                rec_ctrl_msg.data_len = (request->wLength > RECOM_INTERFACE_DATA_BUFFER_SIZE) ? RECOM_INTERFACE_DATA_BUFFER_SIZE : request->wLength;
                if (p_itf->parent->cb.generic.ctrl_cb(p_itf->itf_num, NULL, &rec_ctrl_msg, true)) {
                    return tud_control_xfer(rhport, request, rec_ctrl_msg.buffer, rec_ctrl_msg.data_len);
                }
                return false;
            }
            return false;
        }
        return true;
    } else /* TUSB_DIR_OUT */ {
        if (stage == CONTROL_STAGE_SETUP) {
            if (request->wLength == 0) {
                /* 
                 * The host is not sending us any data, so we can process the request right away.
                 * Since no data is sent, the device is required to respond with a status stage
                 * response. This is done by initiating a control transfer without any data.
                 */
                if (p_itf->parent->cb.generic.ctrl_cb != NULL) {
                    return p_itf->parent->cb.generic.ctrl_cb(p_itf->itf_num, NULL, &rec_ctrl_msg, false) &&
                           tud_control_xfer(rhport, request, NULL, 0);
                }
                return false;
            } else if (request->wLength > p_itf->rx_buffer_size) {
                /* The host is sending us more data than we can handle. Reject it! */
                return false;
            } else {
                /* 
                 * The host is sending us data and since we are in the SETUP stage we need to prepare
                 * the endpoint for receiving this data into our data buffer. Once the data has been
                 * received (DATA stage completes), we will get called again and then process the 
                 * request.
                 */
                return tud_control_xfer(rhport, request, p_itf->rx_buffer, request->wLength);
            }
        } else if (stage == CONTROL_STAGE_DATA) {
            /* 
             * We have received a request with data. Process it.
             * NOTE: That data reception was initiated by the SETUP stage above.
             */
            rec_ctrl_msg.buffer = p_itf->rx_buffer;
            rec_ctrl_msg.data_len = request->wLength;
            if (p_itf->parent->cb.generic.ctrl_cb != NULL) {
                return p_itf->parent->cb.generic.ctrl_cb(p_itf->itf_num, NULL, &rec_ctrl_msg, false);
            }
            return false;
        }
    }

    return false;
}

static bool recom_usbd_xfer_cb(uint8_t rhport, uint8_t ep_addr, xfer_result_t result, uint32_t xferred_bytes)
{
    uint8_t itf;
    struct rec_usb_intf *p_itf;
    bool ret_val;

    /* Determine which interface to use */
    for (itf=0; itf < itf_count; itf++) {
        p_itf = &_recom_usb_itf_arr[itf];
        if ((ep_addr == p_itf->ep_out) || (ep_addr == p_itf->ep_in)) {
            break;
        }
    }
    if (itf >= itf_count) {
        RECOM_DEBUG("RECOM USBD: Invalid interface\n\r");
        return false;
    }

    RECOM_DEBUG("RECOM USBD: DATA Xfer. Itf=%d, EP=0x%02X\n\r", p_itf->itf_num, ep_addr);

    if (ep_addr == p_itf->ep_out) {
        /* Data received from host */
        if (result == XFER_RESULT_SUCCESS &&
            xferred_bytes <= RECOM_INTERFACE_DATA_BUFFER_SIZE) {
            if (p_itf->parent->cb.generic.data_rx_cb) {
                ret_val = p_itf->parent->cb.generic.data_rx_cb(p_itf->itf_num, NULL, p_itf->epout_buf,
                               (uint16_t) xferred_bytes);
            } else {
                ret_val = false;
            }
        }
        /*
         * Now that we have received data, we need to prime the OUT endpoint for the
         * next data packet from the host.
         */
        if (!ret_val || !prime_out_ep(p_itf)) {
            return false;
        }
    } else if (ep_addr == p_itf->ep_in) {
        /*
         * If IN transfer (to host) with length n*64 has been sent, immediately
         * send a zero length packet to indicate end of transfer. There is no
         * need for IN transfer now. It will be executed when the zero length
         * packet completes.
         */
        if (result == XFER_RESULT_SUCCESS &&
            xferred_bytes > 0 && xferred_bytes % 64 == 0) {
                ret_val = usbd_edpt_xfer(TUD_OPT_RHPORT, p_itf->ep_in,
                                  p_itf->epin_buf, 0);
        }
        if (p_itf->parent->cb.generic.data_tx_complete_cb) {
            ret_val = p_itf->parent->cb.generic.data_tx_complete_cb(p_itf->itf_num, xferred_bytes, result!= XFER_RESULT_SUCCESS);
        }
    }

    return true;
}

/*
 * ********************
 * * PUBLIC FUNCTIONS *
 * ********************
 */

static usbd_class_driver_t recom_itf_drv = {
    .init               = recom_usbd_init,
    .reset              = recom_usbd_reset,
    .open               = recom_usbd_open,
    .control_xfer_cb    = recom_usbd_control_xfer_cb,
    .xfer_cb            = recom_usbd_xfer_cb,
    .sof                = NULL,
};

uint8_t recom_usb_generic_interface_register(struct rec_itf * itf, struct rec_itf_config *itf_cfg)
{
    struct rec_usb_itf_desc recom_itf_desc = {
        .itf = {
            .bLength = sizeof(tusb_desc_interface_t),
            .bDescriptorType = TUSB_DESC_INTERFACE,
            .bNumEndpoints = 2,
            .bInterfaceClass = TUSB_CLASS_VENDOR_SPECIFIC,
            .bInterfaceSubClass = itf_cfg->u.generic.interface_id,
            .bInterfaceProtocol = itf_cfg->u.generic.protocol_id,
        },
        .ep_out = {
            .bLength = sizeof(tusb_desc_endpoint_t),
            .bDescriptorType = TUSB_DESC_ENDPOINT,
            .bEndpointAddress = DEFAULT_EP_OUT,
            .bmAttributes = {
                .xfer = TUSB_XFER_BULK,
                .sync = 0,
                .usage = 0,
            },
            .wMaxPacketSize = U16_TO_U8S_LE(RECOM_INTERFACE_DATA_BUFFER_SIZE),
            .bInterval = 0,
        },
        .ep_in = {
            .bLength = sizeof(tusb_desc_endpoint_t),
            .bDescriptorType = TUSB_DESC_ENDPOINT,
            .bEndpointAddress = DEFAULT_EP_IN,
            .bmAttributes = {
                .xfer = TUSB_XFER_BULK,
                .sync = 0,
                .usage = 0,
            },
            .wMaxPacketSize = U16_TO_U8S_LE(RECOM_INTERFACE_DATA_BUFFER_SIZE),
            .bInterval = 0,
        },
    };

    _recom_usb_itf_arr[itf_count].parent = itf;
    _recom_usb_itf_arr[itf_count].interface_id = itf_cfg->u.generic.interface_id;
    _recom_usb_itf_arr[itf_count].protocol_id = itf_cfg->u.generic.protocol_id;
    _recom_usb_itf_arr[itf_count].rx_buffer = itf_cfg->u.generic.rx_buffer;
    _recom_usb_itf_arr[itf_count].rx_buffer_size = itf_cfg->u.generic.rx_buffer_size;

    /*
     * The current counter for the number of registered interfaces (this driver) is
     * the interface ID
     */
    itf->interface_id = itf_count;

    /* Increase the driver counter to prepare for the next one */
    itf_count++;

    RECOM_INFO("Adding interface for %s\n\r", itf_cfg->itf_str);

    return recom_usb_add_interface(&recom_itf_drv, &recom_itf_desc, sizeof(recom_itf_desc), itf_cfg->itf_str);
}

bool recom_usb_generic_itf_set_ctrl_callback(struct rec_itf *itf, rec_ctrl_transfer_cb cb)
{
    itf->cb.generic.ctrl_cb = cb;
    return true;
}

bool recom_usb_generic_itf_set_rx_data_callback(struct rec_itf *itf, rec_data_rx_cb cb)
{
    itf->cb.generic.data_rx_cb = cb;
    return true;
}

bool recom_usb_generic_itf_set_tx_complete_callback(struct rec_itf *itf, rec_data_tx_complete_cb cb)
{
    itf->cb.generic.data_tx_complete_cb = cb;
    return true;
}

bool recom_usb_generic_itf_write(struct rec_itf *itf, uint8_t *p_data, uint32_t num_bytes)
{
    struct rec_usb_intf *p_itf;

    /* Determine which interface to use */
    if (itf->interface_id >= itf_count) {
        return false;
    }

    p_itf = &_recom_usb_itf_arr[itf->interface_id];

    if (num_bytes > RECOM_INTERFACE_DATA_BUFFER_SIZE)
        return false;

    memcpy(p_itf->epin_buf, p_data, num_bytes);
    return usbd_edpt_xfer(TUD_OPT_RHPORT, p_itf->ep_in, p_itf->epin_buf, num_bytes);
}

uint32_t recom_usb_generic_itf_bytes_available(struct rec_itf *itf)
{
    return 0;
}

bool recom_usb_generic_itf_read(struct rec_itf *itf, uint8_t *p_data, uint32_t num_bytes)
{
    return true;
}
