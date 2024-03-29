#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "recom_defs.h"
#include "recom_git_version.h"

static const uint32_t hw_id = 0x00005422;
static const uint32_t hw_rev = 0x00000001;
static const char * fw_rev = "v0.0.1-52d46fa2b";
static const char * serial = "This is a serial number";


bool rec_bdev_process_msg(struct rec_transport_control *ctrl, struct rec_message *msg, bool read)
{
    uint16_t data_len;

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
            memcpy(msg->buffer, (uint8_t *) &hw_id, sizeof(hw_id));
            msg->data_len = sizeof(hw_id);
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEC_CMD_HW_REV:
        if (read) {
            memcpy(msg->buffer, (uint8_t *) &hw_rev, sizeof(hw_rev));
            msg->data_len = sizeof(hw_rev);
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEV_CMD_FW_REV:
        if (read) {
            data_len = strlen(fw_rev);
            if (data_len >= ctrl->max_data_len) {
                return false;
            }
            strlcpy((char *) msg->buffer, fw_rev, ctrl->max_data_len);
            msg->data_len = data_len;
            return true;
        } else {
            return false;
        }
        break;

    case REV_BDEV_CMD_SERIAL:
        if (read) {
            data_len = strlen(serial);
            if (data_len >= ctrl->max_data_len) {
                return false;
            }
            strlcpy((char *) msg->buffer, serial, ctrl->max_data_len);
            msg->data_len = data_len;
            return true;
        } else {
            return false;
        }
        break;

    case REV_BDEV_CMD_RESET:
        if (read) {

        } else {
            return false;
        }
        break;

    case REV_BDEV_CMD_GET_INTF:
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
