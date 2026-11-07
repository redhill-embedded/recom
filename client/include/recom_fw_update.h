#ifndef _RECOM_FW_UPDATE_H_
#define _RECOM_FW_UPDATE_H_

/*
 * RECom firmware update -- device side.
 *
 * RECom carries a firmware image from the host to the device and drives the
 * update workflow; the application does the actual work (storing the image,
 * checking it, arranging for it to be installed) by implementing the
 * callbacks below. RECom makes no assumption about the MCU, the flash, the
 * bootloader or the image format.
 *
 * Host-side sequence (see the RECom README, "Firmware update"):
 *
 *   FW_INFO                  capabilities (chunk size, alignment, max size)
 *   FW_BEGIN(size)           rec_device_fw_begin_cb()
 *     poll FW_STATUS         until not busy (e.g. erase done)
 *   FW_DATA(offset, chunk)   rec_device_fw_write_cb(), repeated
 *   FW_FINISH                rec_device_fw_finish_cb()
 *     poll FW_STATUS         until not busy (e.g. image check done)
 *   FW_APPLY(mode)           rec_device_fw_apply_cb()
 *   RESET(REBOOT)            existing reset command
 *   ... device re-appears ...
 *   FW_IMAGE_INFO            running image version / confirmed
 *
 * Callbacks run in the context that calls recom_task(), in response to host
 * requests, and must return promptly (a host request times out after about
 * a second). Anything longer -- erasing, verifying an image -- should be
 * started by the callback, reported as busy through
 * rec_device_fw_status_cb(), and advanced from rec_device_poll_cb(), which
 * recom_task() calls on every pass.
 *
 * All callbacks are weak; a device that implements none of them simply
 * doesn't support firmware update (the host sees FW_INFO rejected).
 */

#include <stdbool.h>
#include <stdint.h>

/* Result of a firmware-update command. Returned by the callbacks; the host
 * reads the last one back through FW_STATUS (a rejected USB request carries
 * no detail itself). Values are part of the protocol -- do not renumber. */
enum rec_fw_result {
    REC_FW_OK           = 0,
    REC_FW_BUSY         = 1,    /* a previous operation is still running */
    REC_FW_ERR_STATE    = 2,    /* not allowed in the current state */
    REC_FW_ERR_PARAM    = 3,    /* malformed request */
    REC_FW_ERR_SIZE     = 4,    /* image too large / too small */
    REC_FW_ERR_BOUNDS   = 5,    /* write outside the image */
    REC_FW_ERR_ALIGN    = 6,    /* offset/length not aligned */
    REC_FW_ERR_OVERLAP  = 7,    /* range already written */
    REC_FW_ERR_INCOMPLETE = 8,  /* finish before all data arrived */
    REC_FW_ERR_BAD_IMAGE  = 9,  /* image failed the device's checks */
    REC_FW_ERR_UNCONFIRMED = 10, /* running image not yet confirmed */
    REC_FW_ERR_FLASH    = 11,   /* storage error */
    REC_FW_ERR_UNSUPPORTED = 12, /* not implemented by this device */
};

/* Update state reported by FW_STATUS. Values are part of the protocol. */
enum rec_fw_state {
    REC_FW_STATE_IDLE       = 0,
    REC_FW_STATE_PREPARING  = 1,    /* after begin, e.g. erasing */
    REC_FW_STATE_RECEIVING  = 2,    /* accepting FW_DATA */
    REC_FW_STATE_VERIFYING  = 3,    /* after finish, checking the image */
    REC_FW_STATE_READY      = 4,    /* verified, can be applied */
    REC_FW_STATE_APPLIED    = 5,    /* will be installed on next reset */
    REC_FW_STATE_ERROR      = 6,    /* see op_error; abort to recover */
};

/* Image formats the host tool knows how to pre-check. */
enum rec_fw_image_format {
    REC_FW_IMAGE_OPAQUE     = 0,    /* host sends the file as-is */
    REC_FW_IMAGE_MCUBOOT    = 1,    /* MCUboot signed image (imgtool) */
};

/* FW_APPLY modes. */
enum rec_fw_apply_mode {
    REC_FW_APPLY_TEST       = 0,    /* run once; device must confirm it */
    REC_FW_APPLY_PERMANENT  = 1,    /* install permanently */
};

struct rec_fw_info {
    uint8_t image_format;       /* enum rec_fw_image_format */
    uint16_t max_chunk;         /* largest FW_DATA payload; 0 = transport max */
    uint16_t write_align;       /* offsets/lengths must be multiples, except
                                 * the final chunk; 1 = no constraint */
    uint32_t max_image_size;
};

struct rec_fw_status {
    uint8_t state;              /* enum rec_fw_state */
    bool busy;                  /* an operation is in progress; poll again */
    uint8_t op_error;           /* enum rec_fw_result of a failed background
                                 * operation (state ERROR), else REC_FW_OK */
    uint32_t image_size;
    uint32_t bytes_received;
    uint16_t progress_done;     /* progress of the current operation, */
    uint16_t progress_total;    /* e.g. pages erased; 0/0 if not applicable */
};

struct rec_fw_image_info {
    bool confirmed;             /* false: running a test image that will be
                                 * reverted if it doesn't confirm itself */
    bool version_valid;         /* the fields below are meaningful */
    uint8_t major;
    uint8_t minor;
    uint16_t revision;
    uint32_t build;
};

/* Application callbacks (all weak in RECom). Return REC_FW_OK or an error. */
bool rec_device_fw_info_cb(struct rec_fw_info *info);   /* false: unsupported */
uint8_t rec_device_fw_begin_cb(uint32_t image_size);
uint8_t rec_device_fw_write_cb(uint32_t offset, const uint8_t *data, uint16_t len);
uint8_t rec_device_fw_finish_cb(void);
uint8_t rec_device_fw_apply_cb(uint8_t mode);
uint8_t rec_device_fw_abort_cb(void);
bool rec_device_fw_status_cb(struct rec_fw_status *status);
bool rec_device_fw_image_info_cb(struct rec_fw_image_info *info);

/* Called on every recom_task() pass; advance long-running work here. */
void rec_device_poll_cb(void);

#endif /* _RECOM_FW_UPDATE_H_ */
