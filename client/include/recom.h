#ifndef _RECOM_H_
#define _RECOM_H_

#include "recom_defs.h"

bool recom_init(struct rec_config *cfg);
bool recom_task(void);

/**
 * @brief Registers an application interface with RECom
 *
 * @param itf RECom interface handle
 * @param config Pointer to RECom interface configuration data structure
 * @return true
 * @return false
 */
bool recom_interface_register(struct rec_itf_config *config);

/**
 * @brief Returns the number of bytes available at the interface
 *
 * @param itf RECom interface handle
 * @return uint32_t
 */
uint32_t recom_interface_bytes_available(uint8_t itf_num);

/**
 * @brief Reads data from the interface
 *
 * @param itf RECom interface handle
 * @param buffer Pointer to buffer where the read data should be written to
 * @param bytes_to_read Specifies how many bytes to read
 * @return true
 * @return false
 */
bool recom_interface_read(uint8_t itf_num, uint8_t *buffer, uint32_t bytes_to_read);

/**
 * @brief Writes data to the interface
 *
 * @param itf RECom interface handle
 * @param buffer Pointer to data buffer to send
 * @param bytes_to_write Specifies the number of bytes in the buffer
 * @return true
 * @return false
 */
bool recom_interface_write(uint8_t itf_num, uint8_t *buffer, uint32_t bytes_to_write);

#endif /* _RECOM_H_ */
