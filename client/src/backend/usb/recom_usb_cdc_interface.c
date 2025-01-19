#include <tusb.h>

#include "recom_usb_cdc_interface.h"
#include "recom_usb.h"
#include "tusb_config.h"

static uint8_t recom_cdc_uart_itf_count = 0;

typedef struct cdc_itf_desc {
    tusb_desc_interface_assoc_t assoc;
    tusb_desc_interface_t itf_cdc;
    cdc_desc_func_header_t cdc_hdr;
    cdc_desc_func_call_management_t cdc_call;
    cdc_desc_func_acm_t cdc_line;
    cdc_desc_func_union_t cdc_union;
    tusb_desc_endpoint_t ep_int;
    tusb_desc_interface_t itf_data;
    tusb_desc_endpoint_t ep_out;
    tusb_desc_endpoint_t ep_in;
} __attribute__((packed)) cdc_itf_desc_t;


uint8_t recom_usb_cdc_interface_register(struct rec_itf * itf, struct rec_itf_config *itf_cfg)
{
    struct cdc_itf_desc cdc_itf_desc = {
        .assoc = {
            .bLength = sizeof(tusb_desc_interface_assoc_t),
            .bDescriptorType = TUSB_DESC_INTERFACE_ASSOCIATION,
            .bFirstInterface = 0,   // <<=== WILL BE UPDATED WHEN REGISTERING INTERFACE
            .bInterfaceCount = 2,
            .bFunctionClass = TUSB_CLASS_CDC,
            .bFunctionSubClass = CDC_COMM_SUBCLASS_ABSTRACT_CONTROL_MODEL,
            .bFunctionProtocol = CDC_COMM_PROTOCOL_NONE,
            .iFunction = 0,
        },
        .itf_cdc = {
            .bLength = sizeof(tusb_desc_interface_t),
            .bDescriptorType = TUSB_DESC_INTERFACE,
            .bNumEndpoints = 1,
            .bInterfaceClass = TUSB_CLASS_CDC,
            .bInterfaceSubClass = CDC_COMM_SUBCLASS_ABSTRACT_CONTROL_MODEL,
            .bInterfaceProtocol = CDC_COMM_PROTOCOL_NONE,
        },
        .cdc_hdr = {
            .bLength = sizeof(cdc_desc_func_header_t),
            .bDescriptorType = TUSB_DESC_CS_INTERFACE,
            .bDescriptorSubType = CDC_FUNC_DESC_HEADER,
            .bcdCDC = 0x0120,
        },
        .cdc_call = {
            .bLength = sizeof(cdc_desc_func_call_management_t),
            .bDescriptorType = TUSB_DESC_CS_INTERFACE,
            .bDescriptorSubType = CDC_FUNC_DESC_CALL_MANAGEMENT,
            .bmCapabilities = {0},
            .bDataInterface = 0,    // <<=== WILL BE UPDATED WHEN REGISTERING INTERFACE
        },
        .cdc_line = {
            .bLength = sizeof(cdc_desc_func_acm_t),
            .bDescriptorType = TUSB_DESC_CS_INTERFACE,
            .bDescriptorSubType = CDC_FUNC_DESC_ABSTRACT_CONTROL_MANAGEMENT,
            .bmCapabilities = {
                .support_comm_request = 0,  ///< Device supports the request combination of Set_Comm_Feature, Clear_Comm_Feature, and Get_Comm_Feature.
                .support_line_request = 0,  ///< Device supports the request combination of Set_Line_Coding, Set_Control_Line_State, Get_Line_Coding, and the notification Serial_State.
                .support_send_break = 0,    ///< Device supports the request Send_Break
                .support_notification_network_connection = 0,  ///< Device supports the notification Network_Connection.
            },
        },
        .cdc_union = {
            .bLength = sizeof(cdc_desc_func_union_t),
            .bDescriptorType = TUSB_DESC_CS_INTERFACE,
            .bDescriptorSubType = CDC_FUNC_DESC_UNION,
            .bControlInterface = 0,     // <<=== WILL BE UPDATED WHEN REGISTERING INTERFACE
            .bSubordinateInterface = 0, // <<=== WILL BE UPDATED WHEN REGISTERING INTERFACE
        },
        .ep_int = {
            .bLength = sizeof(tusb_desc_endpoint_t),
            .bDescriptorType = TUSB_DESC_ENDPOINT,
            .bEndpointAddress = 0x80,
            .bmAttributes = {
                .xfer = TUSB_XFER_INTERRUPT,
                .sync = 0,
                .usage = 0,
            },
            .wMaxPacketSize = U16_TO_U8S_LE(16),
            .bInterval = 16,
        },
        .itf_data = {
            .bLength = sizeof(tusb_desc_interface_t),
            .bDescriptorType = TUSB_DESC_INTERFACE,
            .bNumEndpoints = 2,
            .bInterfaceClass = TUSB_CLASS_CDC_DATA,
            .bInterfaceSubClass = 0,
            .bInterfaceProtocol = 0,
        },
        .ep_out = {
            .bLength = sizeof(tusb_desc_endpoint_t),
            .bDescriptorType = TUSB_DESC_ENDPOINT,
            .bEndpointAddress = 0x00,
            .bmAttributes = {
                .xfer = TUSB_XFER_BULK,
                .sync = 0,
                .usage = 0,
            },
            .wMaxPacketSize = U16_TO_U8S_LE(64),
            .bInterval = 0,
        },
        .ep_in = {
            .bLength = sizeof(tusb_desc_endpoint_t),
            .bDescriptorType = TUSB_DESC_ENDPOINT,
            .bEndpointAddress = 0x80,
            .bmAttributes = {
                .xfer = TUSB_XFER_BULK,
                .sync = 0,
                .usage = 0,
            },
            .wMaxPacketSize = U16_TO_U8S_LE(64),
            .bInterval = 0,
        },
    };

    /* Keep track of how many CDC interfaces have been registered and make sure that we
     * don't exceed the number of actual CDC interfaces configured with the TinyUSB stack.
     */
    recom_cdc_uart_itf_count++;
    if (recom_cdc_uart_itf_count > CFG_TUD_CDC)
        return false;

    return recom_usb_add_interface(NULL, &cdc_itf_desc, sizeof(cdc_itf_desc), itf_cfg->itf_str);
}

bool recom_usb_cdc_interface_write(struct rec_itf * itf, uint8_t *p_data, uint32_t num_bytes)
{
    uint32_t bytes_written;

    bytes_written = tud_cdc_n_write(itf->sub_interface_id, p_data, num_bytes);
    if (bytes_written != num_bytes)
        return false;
    tud_cdc_n_write_flush(itf->sub_interface_id);
    return true;
}

uint32_t recom_usb_cdc_interface_bytes_available(struct rec_itf * itf)
{
    return tud_cdc_n_available(itf->sub_interface_id);
}

bool recom_usb_cdc_interface_read(struct rec_itf * itf, uint8_t *p_data, uint32_t num_bytes)
{
    uint32_t bytes_read;

    bytes_read = tud_cdc_n_read(itf->sub_interface_id, p_data, num_bytes);
    if (bytes_read != num_bytes)
        return false;
    return true;
}
