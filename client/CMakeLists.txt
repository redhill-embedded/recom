
set(RECOM_BASE_DIR ${CMAKE_CURRENT_LIST_DIR})

set(RECOM_SOURCES
    ${RECOM_BASE_DIR}/src/recom.c
    ${RECOM_BASE_DIR}/src/recom_base_device.c
    ${RECOM_BASE_DIR}/src/backend/recom_usb.c
    ${RECOM_BASE_DIR}/src/backend/recom_usb_interface.c
)

set(RECOM_INCLUDE_DIRS
    ${RECOM_BASE_DIR}/include
    ${RECOM_BASE_DIR}/include/backend
)
