#ifndef _RECOM_H_
#define _RECOM_H_

#include "recom_defs.h"

bool recom_init(struct rec_config *cfg);
bool recom_task(void);

/**
 * @brief Registers an application interface with RECom and initializes the interface
 *        to its default values (i.e. all callbacks set to NULL)
 *
 * @param itf Pointer to RECom interface handle
 * @param config Pointer to RECom interface configuration data structure
 * @return true
 * @return false
 */
bool recom_itf_register(struct rec_itf *itf, struct rec_itf_config *config);

/**
 * @brief Registers a control callback function with the interface. To deregister a
 *        callback, a NULL pointer can be passed in.
 *
 * @param itf Pointer to RECom interface handle
 * @param cb The control callback function
 */
void recom_itf_set_ctrl_callback(struct rec_itf *itf, rec_ctrl_transfer_cb cb);

/**
 * @brief Registers a data received callback with the interface. To deregister a
 *        callback, a NULL pointer can be passed in.
 *
 * @param itf Pointer to RECom interface handle
 * @param cb The data received callback function
 */
void recom_itf_set_data_rx_callback(struct rec_itf *itf, rec_data_rx_cb cb);

/**
 * @brief Registers a data transmission complete callback with the interface.
 *        This callback is triggered when a data transmission completes either due to a
 *        successfull transfer or an error. To deregister a callback, a NULL pointer can
 *        be passed in.
 *
 * @param itf Pointer to RECom interface handle
 * @param cb The transfer complete callback function
 */
void recom_itf_set_transmit_complete_callback(struct rec_itf *itf, rec_data_tx_complete_cb cb);

/**
 * @brief Returns the number of bytes available at the interface
 *
 * @param itf RECom interface handle
 * @return uint32_t
 */
uint32_t recom_itf_bytes_available(struct rec_itf *itf);

/**
 * @brief Reads data from the interface
 *
 * @param itf Pointer to RECom interface handle
 * @param buffer Pointer to buffer where the read data should be written to
 * @param bytes_to_read Specifies how many bytes to read
 * @return true
 * @return false
 */
bool recom_itf_read(struct rec_itf *itf, uint8_t *buffer, uint32_t bytes_to_read);

/**
 * @brief Writes data to the interface
 *
 * @param itf Pointer to RECom interface handle
 * @param buffer Pointer to data buffer to send
 * @param bytes_to_write Specifies the number of bytes in the buffer
 * @return true
 * @return false
 */
bool recom_itf_write(struct rec_itf *itf, uint8_t *buffer, uint32_t bytes_to_write);

#endif /* _RECOM_H_ */
