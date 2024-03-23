#include <stdbool.h>
#include <stdint.h>

#include "recom_defs.h"
#include "backend/usb/recom_usb.h"
#include "backend/usb/recom_usb_interface.h"

static enum rec_transport_type trans_type = eREC_TRANSPORT_TYPE_NONE;

bool recom_init(struct rec_config *cfg)
{
    trans_type = cfg->type;
    if (cfg->type == eREC_TRANSPORT_TYPE_USB) {
        return recom_usb_init(cfg);
    } else if (cfg->type == eREC_TRANSPORT_TYPE_UART) {
        return false;
    }
    return false;
}

bool recom_task(void)
{
    if (trans_type == eREC_TRANSPORT_TYPE_USB) {
        return recom_usb_task();
    } else if (trans_type == eREC_TRANSPORT_TYPE_UART) {
        return false;
    }
    return false;
}

/*
 * *****************
 * * INTERFACE API *
 * *****************
 */

bool recom_interface_register(struct rec_itf_config *config)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_interface_register(config);
}

uint32_t recom_interface_bytes_available(uint8_t itf_num)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_interface_bytes_available(itf_num);
}

bool recom_interface_read(uint8_t itf_num, uint8_t *buffer, uint32_t bytes_to_read)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_interface_read(itf_num, buffer, bytes_to_read);
}

bool recom_interface_write(uint8_t itf_num, uint8_t *buffer, uint32_t bytes_to_write)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_interface_write(itf_num, buffer, bytes_to_write);
}
