
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

# Extract the current Recom version from git tag
execute_process(
    COMMAND git describe --tags --dirty
    WORKING_DIRECTORY ${RECOM_BASE_DIR}
    OUTPUT_VARIABLE RECOM_GIT_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)

# Check if git tag was found
if(NOT RECOM_GIT_VERSION)
    set(RECOM_GIT_VERSION "Unknown")
endif()

# Print and save to file
message(STATUS "RECOM_GIT_VERSION: ${RECOM_GIT_VERSION}")
file(WRITE ${RECOM_BASE_DIR}/include/recom_git_version.h "#ifndef RECOM_GIT_VERSION_H\n#define RECOM_GIT_VERSION_H\n\n#define RECOM_GIT_VERSION \"${RECOM_GIT_VERSION}\"\n\n#endif")
