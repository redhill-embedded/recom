#ifndef _RECOM_DEFS_H_
#define _RECOM_DEFS_H_

#include <stdbool.h>
#include <stdint.h>

#include "recom_config.h"

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
    REC_BDEV_CMD_SCRATCH    = 0,
    REC_BDEV_CMD_HW_ID      = 1,
    REC_BDEC_CMD_HW_REV     = 2,
    REC_BDEV_CMD_FW_REV     = 3,
    REV_BDEV_CMD_SERIAL     = 4,
    REV_BDEV_CMD_RESET      = 5,
    REV_BDEV_CMD_GET_INTF   = 6,
};

typedef void (*recom_app_ctrl_cb)(bool read, uint8_t request, uint8_t *data, uint16_t data_len);
typedef void (*recom_app_data_cb)(uint8_t * data, uint16_t data_len);

typedef struct rec_itf_config {
    recom_app_ctrl_cb ctrl_cb;
    recom_app_data_cb data_cb;
    uint8_t interface_id;
    uint8_t protocol_id;
    char * app_str;
    uint8_t *rx_buffer;
    uint8_t *tx_buffer;
    uint32_t rx_buffer_size;
    uint32_t tx_buffer_size;
} rec_itf_config_t;

typedef struct rec_itf {
    uint8_t itf_id;
} rec_itf_t;

#endif /* _RECOM_DEFS_H_ */