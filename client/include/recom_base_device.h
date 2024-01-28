#ifndef _RECOM_BASE_DEVICE_H_
#define _RECOM_BASE_DEVICE_H_

#include "recom_defs.h"

bool rec_bdev_process_msg(struct rec_transport_control *ctrl, struct rec_message *msg, bool read);

#endif /* _RECOM_BASE_DEVICE_H_ */
