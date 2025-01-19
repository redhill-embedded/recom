#ifndef _RECOM_DEFS_H_
#define _RECOM_DEFS_H_

#include <stdbool.h>
#include <stdint.h>

#include "recom_config.h"

/* Magic Recom device identifier.
 * This is used for identifying devices as Recom enabled device during the
 * detection process.
 * DO NOT CHANGE!!!
 */
#define RECOM_DEVICE_ID     (0x53C08A30)

/* Recom protocol version
 * This is increased every-time a protocol change is made.
 */
#define RECOM_PROTOCOL_VER  (0x0001)

#ifndef RECOM_INFO
#define RECOM_INFO(...) ((void) 0)
#endif

#ifndef RECOM_DEBUG
#define RECOM_DEBUG(...) ((void) 0)
#endif

enum rec_transport_type {
    eREC_TRANSPORT_TYPE_NONE = 0,
    eREC_TRANSPORT_TYPE_USB,
    eREC_TRANSPORT_TYPE_UART
};

struct rec_transport_control {
    enum rec_transport_type type;
    uint16_t max_data_len;
};

struct rec_config {
    enum rec_transport_type type;
    uint16_t vendor_id;
    uint16_t product_id;
    char * vendor_str;
    char * product_str;
    char * serial_str;
};

struct rec_message {
    uint8_t cmd;
    uint16_t index;
    uint16_t value;
    uint16_t data_len;
    uint8_t *buffer;
};

enum rec_bdev_req_type {
    REC_BDEV_CMD_DEV_ID     = 0,
    REC_BDEV_CMD_HW_ID      = 1,
    REC_BDEC_CMD_HW_REV     = 2,
    REC_BDEV_CMD_FW_REV     = 3,
    REC_BDEV_CMD_SERIAL     = 4,
    REC_BDEV_CMD_RESET      = 5,
    REC_BDEV_CMD_GET_INTF   = 6,
};

enum rec_bdev_reset_opt {
    REC_RST_OPT_REBOOT      = 0,    /* Reset the device and reboot back to the application */
    REC_RST_OPT_BOOTLOADER  = 1,    /* Reset to bootloader */
    REC_RST_OPT_ROM_BOOT    = 2,    /* Reset to built-in ROM bootloader */
};

typedef enum rec_itf_type {
    eREC_ITF_TYPE_INVALID   = 0,
    eREC_ITF_TYPE_GENERIC   = 1,
    eREC_ITF_TYPE_USB_CDC   = 2,
} rec_itf_type_t;

typedef bool (*rec_ctrl_transfer_cb)(uint8_t itf_num,
                                       struct rec_transport_control *ctrl,
                                       struct rec_message *msg, bool read);
typedef bool (*rec_data_rx_cb)(uint8_t itf_num,
                                 struct rec_transport_control *ctrl,
                                 uint8_t *data, uint16_t data_len);

typedef bool (*rec_data_tx_complete_cb)(uint8_t itf_num, uint32_t data_len,
                                        bool is_error);

typedef void (*rec_usb_driver_cb)(uint8_t itf_num);

typedef struct rec_usb_generic_itf {
    uint8_t interface_id;
    uint8_t protocol_id;
    char * app_str;
    uint8_t *rx_buffer;
    uint8_t *tx_buffer;
    uint32_t rx_buffer_size;
    uint32_t tx_buffer_size;
} rec_usb_generic_itf_t;

typedef struct rec_usb_cdc_itf {

} rec_usb_cdc_itf_t;

typedef struct rec_itf_config {
    enum rec_itf_type type;
    char *itf_str;
    union {
        struct rec_usb_generic_itf  generic;
        struct rec_usb_cdc_itf      cdc_uart;
    } u;
} rec_itf_config_t;

typedef struct rec_itf {
    uint8_t interface_id;
    uint8_t sub_interface_id;
    enum rec_itf_type type;
    rec_ctrl_transfer_cb ctrl_cb;
    rec_data_rx_cb data_rx_cb;
    rec_data_tx_complete_cb data_tx_complete_cb;
    rec_usb_driver_cb driver_open_cb;
    rec_usb_driver_cb driver_reset_cb;
} rec_itf_t;

#endif /* _RECOM_DEFS_H_ */
