#ifndef _RECOM_USB_H_
#define _RECOM_USB_H_

#include <tusb.h>
#include <device/usbd_pvt.h>

#include "recom_defs.h"

#define TUD_EP_IN   (0x80)
#define TUD_EP_OUT  (0x00)

#define TUSBD_CLASS_DRIVERS_MAX (8)
#define TUSB_CONF_DESC_SZ (512)

bool recom_usb_init(struct rec_config *cfg);
bool recom_usb_task(void);
bool recom_usb_add_interface(usbd_class_driver_t* drv,
                              const void *desc, unsigned int desc_len,
                              const char *str);

#endif /* _RECOM_USB_H_ */
