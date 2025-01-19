#include <stdbool.h>
#include <stdint.h>

#include "recom_defs.h"
#include "backend/usb/recom_usb.h"
#include "backend/usb/recom_usb_generic_interface.h"
#include "backend/usb/recom_usb_cdc_interface.h"

static enum rec_transport_type trans_type = eREC_TRANSPORT_TYPE_NONE;

static uint8_t interface_count = 0;

bool recom_init(struct rec_config *cfg)
{
    bool ret;

    trans_type = cfg->type;
    if (cfg->type == eREC_TRANSPORT_TYPE_USB) {
        ret = recom_usb_init(cfg);
    } else if (cfg->type == eREC_TRANSPORT_TYPE_UART) {
        ret = false;
    }
    if (ret == true) {
        interface_count++;
    }
    return ret;
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

bool recom_itf_register(struct rec_itf *itf, struct rec_itf_config *config)
{
    itf->interface_id = interface_count;
    itf->type = config->type;

    /* Set all callback function pointers to NULL */
    itf->ctrl_cb = NULL;
    itf->data_rx_cb = NULL;
    itf->data_tx_complete_cb = NULL;
    itf->driver_reset_cb = NULL;
    itf->driver_open_cb = NULL;

    switch (config->type) {
    case eREC_ITF_TYPE_GENERIC:
        return recom_usb_generic_interface_register(itf, config);
        break;
    case eREC_ITF_TYPE_USB_CDC:
        return recom_usb_cdc_interface_register(itf, config);
        break;
    default:
        itf-> type = eREC_ITF_TYPE_INVALID;
        return false;
    }

    /* Should never get here */
    return false;
}

void recom_itf_set_ctrl_callback(struct rec_itf *itf, rec_ctrl_transfer_cb cb)
{
    itf->ctrl_cb = cb;
}

void recom_itf_set_rx_data_callback(struct rec_itf *itf, rec_data_rx_cb cb)
{
    itf->data_rx_cb = cb;
}

void recom_itf_set_tx_complete_callback(struct rec_itf *itf, rec_data_tx_complete_cb cb)
{
    itf->data_tx_complete_cb = cb;
}

uint32_t recom_itf_bytes_available(struct rec_itf *itf)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_generic_interface_bytes_available(itf);
}

bool recom_itf_read(struct rec_itf *itf, uint8_t *buffer, uint32_t bytes_to_read)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_generic_interface_read(itf, buffer, bytes_to_read);
}

bool recom_itf_write(struct rec_itf *itf, uint8_t *buffer, uint32_t bytes_to_write)
{
    /*
     * For now this is a simple wrapper around the USB interface.
     * Replace with backend selector once more backends are added.
     */
    return recom_usb_generic_interface_write(itf, buffer, bytes_to_write);
}
