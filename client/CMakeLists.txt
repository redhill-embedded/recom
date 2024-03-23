
set(RECOM_BASE_DIR ${CMAKE_CURRENT_LIST_DIR})

set(RECOM_SOURCES
    ${RECOM_BASE_DIR}/src/recom.c
    ${RECOM_BASE_DIR}/src/recom_base_device.c
    ${RECOM_BASE_DIR}/src/backend/usb/recom_usb.c
    ${RECOM_BASE_DIR}/src/backend/usb/recom_usb_interface.c
    PARENT_SCOPE
)

set(RECOM_INCLUDE_DIRS
    ${RECOM_BASE_DIR}/include
    ${RECOM_BASE_DIR}/include/backend/usb
    PARENT_SCOPE
)
