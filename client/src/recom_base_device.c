#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "recom_defs.h"
#include "recom_fw_update.h"
#include "recom_git_version.h"

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

__attribute__((weak)) size_t rec_device_serial_cb(uint8_t index, const char **p_serial)
{
    *p_serial = "0";
    return 1;
}

__attribute__((weak)) bool rec_device_reset_cb(uint8_t reset_option)
{
    return false;
}

/* Copies up to max_len bytes of the device's log into buffer, starting
 * at logical byte `offset` from the oldest byte still available (0 =
 * oldest). Returns the number of bytes copied; the default (no log
 * available) returns 0, which read() below also treats as "no data at
 * or beyond offset". */
__attribute__((weak)) size_t rec_device_log_read_cb(uint16_t offset, uint8_t *buffer, size_t max_len)
{
    return 0;
}


/* Firmware update: all unsupported by default (see recom_fw_update.h). */
__attribute__((weak)) bool rec_device_fw_info_cb(struct rec_fw_info *info)
{
    (void) info;
    return false;
}

__attribute__((weak)) uint8_t rec_device_fw_begin_cb(uint32_t image_size)
{
    (void) image_size;
    return REC_FW_ERR_UNSUPPORTED;
}

__attribute__((weak)) uint8_t rec_device_fw_write_cb(uint32_t offset, const uint8_t *data,
                                                     uint16_t len)
{
    (void) offset;
    (void) data;
    (void) len;
    return REC_FW_ERR_UNSUPPORTED;
}

__attribute__((weak)) uint8_t rec_device_fw_finish_cb(void)
{
    return REC_FW_ERR_UNSUPPORTED;
}

__attribute__((weak)) uint8_t rec_device_fw_apply_cb(uint8_t mode)
{
    (void) mode;
    return REC_FW_ERR_UNSUPPORTED;
}

__attribute__((weak)) uint8_t rec_device_fw_abort_cb(void)
{
    return REC_FW_ERR_UNSUPPORTED;
}

__attribute__((weak)) bool rec_device_fw_status_cb(struct rec_fw_status *status)
{
    (void) status;
    return false;
}

__attribute__((weak)) bool rec_device_fw_image_info_cb(struct rec_fw_image_info *info)
{
    (void) info;
    return false;
}

__attribute__((weak)) void rec_device_poll_cb(void)
{
}

/* Result of the last firmware-update command, reported by FW_STATUS: a
 * rejected request reaches the host only as a stall, without a reason. */
static uint8_t fw_last_result = REC_FW_OK;

static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t) v;
    p[1] = (uint8_t) (v >> 8);
}

static void put_u32(uint8_t *p, uint32_t v)
{
    put_u16(p, (uint16_t) v);
    put_u16(p + 2, (uint16_t) (v >> 16));
}

static uint32_t get_u32(const uint8_t *p)
{
    return (uint32_t) p[0] | ((uint32_t) p[1] << 8) | ((uint32_t) p[2] << 16) |
           ((uint32_t) p[3] << 24);
}

/* Records a firmware-update command's result; the request succeeds only on
 * REC_FW_OK. */
static bool fw_result(uint8_t result)
{
    fw_last_result = result;
    return result == REC_FW_OK;
}

/*
 * Firmware-update requests. Payloads are little-endian, byte-packed:
 *
 *   FW_INFO (read, 12 bytes):
 *     u8 info_version (1), u8 image_format, u16 max_chunk, u16 write_align,
 *     u16 reserved, u32 max_image_size
 *   FW_BEGIN (write): u32 image_size
 *   FW_DATA (write): the chunk; offset = (value << 16) | index
 *   FW_FINISH, FW_ABORT (write): no data
 *   FW_APPLY (write): u8 mode (enum rec_fw_apply_mode)
 *   FW_STATUS (read, 16 bytes):
 *     u8 state, u8 flags (bit 0: busy), u8 last_result, u8 op_error,
 *     u32 image_size, u32 bytes_received, u16 progress_done,
 *     u16 progress_total
 *   FW_IMAGE_INFO (read, 12 bytes):
 *     u8 flags (bit 0: confirmed, bit 1: version valid), u8 major,
 *     u8 minor, u8 reserved, u16 revision, u16 reserved, u32 build
 */
static bool rec_bdev_process_fw_msg(struct rec_transport_control *ctrl,
                                    struct rec_message *msg, bool read)
{
    switch (msg->cmd) {
    case REC_BDEV_CMD_FW_INFO: {
        struct rec_fw_info info = {0};
        if (!read || ctrl->max_data_len < 12 || !rec_device_fw_info_cb(&info)) {
            return false;
        }
        uint16_t max_chunk = info.max_chunk;
        if (max_chunk == 0 || max_chunk > ctrl->max_data_len) {
            max_chunk = ctrl->max_data_len;
        }
        msg->buffer[0] = 1;
        msg->buffer[1] = info.image_format;
        put_u16(&msg->buffer[2], max_chunk);
        put_u16(&msg->buffer[4], info.write_align ? info.write_align : 1);
        put_u16(&msg->buffer[6], 0);
        put_u32(&msg->buffer[8], info.max_image_size);
        msg->data_len = 12;
        return true;
    }

    case REC_BDEV_CMD_FW_BEGIN:
        if (read) {
            return false;
        }
        if (msg->data_len != 4) {
            return fw_result(REC_FW_ERR_PARAM);
        }
        return fw_result(rec_device_fw_begin_cb(get_u32(msg->buffer)));

    case REC_BDEV_CMD_FW_DATA:
        if (read) {
            return false;
        }
        if (msg->data_len == 0) {
            return fw_result(REC_FW_ERR_PARAM);
        }
        return fw_result(rec_device_fw_write_cb(((uint32_t) msg->value << 16) | msg->index,
                                                msg->buffer, msg->data_len));

    case REC_BDEV_CMD_FW_FINISH:
        if (read) {
            return false;
        }
        return fw_result(rec_device_fw_finish_cb());

    case REC_BDEV_CMD_FW_APPLY:
        if (read) {
            return false;
        }
        if (msg->data_len != 1) {
            return fw_result(REC_FW_ERR_PARAM);
        }
        return fw_result(rec_device_fw_apply_cb(msg->buffer[0]));

    case REC_BDEV_CMD_FW_ABORT:
        if (read) {
            return false;
        }
        return fw_result(rec_device_fw_abort_cb());

    case REC_BDEV_CMD_FW_STATUS: {
        struct rec_fw_status st = {0};
        if (!read || ctrl->max_data_len < 16 || !rec_device_fw_status_cb(&st)) {
            return false;
        }
        msg->buffer[0] = st.state;
        msg->buffer[1] = st.busy ? 0x01 : 0x00;
        msg->buffer[2] = fw_last_result;
        msg->buffer[3] = st.op_error;
        put_u32(&msg->buffer[4], st.image_size);
        put_u32(&msg->buffer[8], st.bytes_received);
        put_u16(&msg->buffer[12], st.progress_done);
        put_u16(&msg->buffer[14], st.progress_total);
        msg->data_len = 16;
        return true;
    }

    case REC_BDEV_CMD_FW_IMAGE_INFO: {
        struct rec_fw_image_info ii = {0};
        if (!read || ctrl->max_data_len < 12 || !rec_device_fw_image_info_cb(&ii)) {
            return false;
        }
        msg->buffer[0] = (ii.confirmed ? 0x01 : 0x00) | (ii.version_valid ? 0x02 : 0x00);
        msg->buffer[1] = ii.major;
        msg->buffer[2] = ii.minor;
        msg->buffer[3] = 0;
        put_u16(&msg->buffer[4], ii.revision);
        put_u16(&msg->buffer[6], 0);
        put_u32(&msg->buffer[8], ii.build);
        msg->data_len = 12;
        return true;
    }

    default:
        return false;
    }
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
            strcpy((char *) &msg->buffer[6], RECOM_GIT_VERSION);
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
            p_str = (char *) rec_device_fw_rev_cb();
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
            data_len = rec_device_serial_cb(msg->index, &p_str);
            if (data_len >= ctrl->max_data_len || data_len == 0) {
                return false;
            }
            memcpy((char *) msg->buffer, p_str, data_len);
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

    case REC_BDEV_CMD_LOG_READ:
        if (read) {
            size_t n = rec_device_log_read_cb(msg->index, msg->buffer, ctrl->max_data_len);
            if (n > ctrl->max_data_len) {
                /* rec_device_log_read_cb() violated its own contract. */
                return false;
            }
            msg->data_len = (uint16_t) n;
            return true;
        } else {
            return false;
        }
        break;

    case REC_BDEV_CMD_FW_INFO:
    case REC_BDEV_CMD_FW_BEGIN:
    case REC_BDEV_CMD_FW_DATA:
    case REC_BDEV_CMD_FW_FINISH:
    case REC_BDEV_CMD_FW_APPLY:
    case REC_BDEV_CMD_FW_ABORT:
    case REC_BDEV_CMD_FW_STATUS:
    case REC_BDEV_CMD_FW_IMAGE_INFO:
        return rec_bdev_process_fw_msg(ctrl, msg, read);

    default:
        return false;
    }
    /* Should never get here */
    return false;
}
