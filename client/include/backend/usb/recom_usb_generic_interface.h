#ifndef _RECOM_USB_GENERIC_INTERFACE_H_
#define _RECOM_USB_GENERIC_INTERFACE_H_

#include <stdbool.h>
#include <stdint.h>

#include "recom_defs.h"


uint8_t recom_usb_generic_interface_register(struct rec_itf *itf, struct rec_itf_config *itf_cfg);

bool recom_usb_generic_interface_write(struct rec_itf *itf, uint8_t *p_data, uint32_t num_bytes);
uint32_t recom_usb_generic_interface_bytes_available(struct rec_itf *itf);
bool recom_usb_generic_interface_read(struct rec_itf *itf, uint8_t *p_data, uint32_t num_bytes);

#endif /* _RECOM_USB_GENERIC_INTERFACE_H_ */
