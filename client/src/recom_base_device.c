#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "recom_defs.h"
#include "recom_git_version.h"

static const uint32_t hw_id = 0x00005422;
static const uint32_t hw_rev = 0x00000001;
static const char * fw_rev = "v0.0.1-52d46fa2b";
static const char * serial = "This is a serial number";

__attribute__((weak)) uint32_t rec_device_hw_id_cb(void)
{
    return 0;
}

__attribute__((weak)) uint32_t rec_device_hw_rev_cb(void)
{
    return 0;
}

__attribute__((weak)) const char * rec_device_fw_rev_cb(void)
{
    return "0.0.0";
}

__attribute__((weak)) const char * rec_device_serial_cb(void)
{
    return "0";
}

__attribute__((weak)) bool rec_device_reset_cb(uint8_t reset_option)
{
    return false;
}


bool rec_bdev_process_msg(struct rec_transport_control *ctrl, struct rec_message *msg, bool read)
{
    uint16_t data_len;
    uint32_t temp32;
    const char * p_str;

    switch (msg->cmd) {
    
    case REC_BDEV_CMD_DEV_ID:
        if (read) {
            uint32_t recom_dev_id = RECOM_DEVICE_ID;
            memcpy(msg->buffer, (uint8_t *) &recom_dev_id, 4);
            uint16_t recom_prot_ver = RECOM_PROTOCOL_VER;
            memcpy(&msg->buffer[4], (uint8_t *) &recom_prot_ver, 2);
            strcpy(&msg->buffer[6], RECOM_GIT_VERSION);
            msg->data_len = 6 + strlen(RECOM_GIT_VERSION);
            return true;
        } else {
            return false;
        }

        break;

    case REC_BDEV_CMD_HW_ID:
        if (read) {
            temp32 = rec_device_hw_id_cb();
            memcpy(msg->buffer, (uint8_t *) &temp32, 4);
            msg->data_len = 4;
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEC_CMD_HW_REV:
        if (read) {
            temp32 = rec_device_hw_rev_cb();
            memcpy(msg->buffer, (uint8_t *) &temp32, 4);
            msg->data_len = 4;
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEV_CMD_FW_REV:
        if (read) {
            p_str = rec_device_fw_rev_cb();
            data_len = strlen(p_str);
            if (data_len >= ctrl->max_data_len) {
                return false;
            }
            strlcpy((char *) msg->buffer, p_str, ctrl->max_data_len);
            msg->data_len = data_len;
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEV_CMD_SERIAL:
        if (read) {
            p_str = rec_device_serial_cb();
            data_len = strlen(p_str);
            if (data_len >= ctrl->max_data_len) {
                return false;
            }
            strlcpy((char *) msg->buffer, p_str, ctrl->max_data_len);
            msg->data_len = data_len;
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEV_CMD_RESET:
        if (read) {

        } else {
            if (msg->data_len == 1) {
                return rec_device_reset_cb(msg->buffer[0]);
            }
            return false;
        }
        break;

    case REC_BDEV_CMD_GET_INTF:
        if (read) {

        } else {
            return false;
        }
        break;

    default:
        return false;
    }
    /* Should never get here */
    return false;
}
