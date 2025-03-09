#ifndef _RECOM_USB_CDC_INTERFACE_H_
#define _RECOM_USB_CDC_INTERFACE_H_

#include <stdbool.h>
#include <stdint.h>

#include "recom_defs.h"


uint8_t recom_usb_cdc_interface_register(struct rec_itf * itf, struct rec_itf_config *itf_cfg);

bool recom_usb_cdc_itf_set_state_callback(struct rec_itf *itf, rec_usb_cdc_state_cb cb);
bool recom_usb_cdc_itf_set_line_coding_callback(struct rec_itf *itf, rec_usb_cdc_line_coding_cb cb);

bool recom_usb_cdc_itf_write(struct rec_itf * itf, uint8_t *p_data, uint32_t num_bytes);
uint32_t recom_usb_cdc_itf_bytes_available(struct rec_itf * itf);
bool recom_usb_cdc_itf_read(struct rec_itf * itf, uint8_t *p_data, uint32_t num_bytes);

#endif /* _RECOM_USB_CDC_INTERFACE_H_ */
