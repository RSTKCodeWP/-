cmake_minimum_required(VERSION 3.22)

# 1. Define Project and Language
project(FlightController_FW C CXX ASM)

# 2. Global Toolchain/Environment Options
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_C_COMPILER arm-none-eabi-gcc)
set(CMAKE_CXX_COMPILER arm-none-eabi-g++)
set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

# Define global architecture flags as a list to prevent string collisions
set(ARCH_FLAGS "-mcpu=cortex-m7" "-mthumb" "-mfpu=fpv5-d16" "-mfloat-abi=hard")

# ========================================================================== #
# SUBSYSTEM BUILD CONFIGURATION
# ========================================================================== #
#############################################################################################################################
############################################ 4. DSP Subsystem (RESTORED)
# file(GLOB_RECURSE DSP_SOURCES "DSP/*.c")
# add_library(dsp_subsystem STATIC ${DSP_SOURCES})
# target_include_directories(dsp_subsystem PUBLIC 
#DSP
#scheduler
#headers
#Drivers/CMSIS/Include
#Drivers/CMSIS/Device/ST/STM32H7xx/Include
#)
# target_compile_options(dsp_subsystem PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)
#target_compile_definitions(dsp_subsystem PRIVATE STM32H723xx)
####################################### Clock Drivers
file(GLOB_RECURSE CLOCK_SOURCES CONFIGURE_DEPENDS "Clocks/*.c")
add_library(clock_library STATIC ${CLOCK_SOURCES})
target_include_directories(clock_library PUBLIC 
headers
STM32H7/CMSIS/Include
STM32H7/CMSIS/Device/ST/STM32H7xx/Include
)
target_link_libraries(clock_library PUBLIC 
scheduler_library
)

target_compile_options(clock_library PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)
target_compile_definitions(clock_library PRIVATE STM32H723xx)
####################################### Peripheral Drivers
file(GLOB_RECURSE PERIPH_SOURCES CONFIGURE_DEPENDS "PeriphDrivers/*.c")
add_library(periph_library STATIC ${PERIPH_SOURCES})
target_include_directories(periph_library PUBLIC 
headers
STM32H7/CMSIS/Include
STM32H7/CMSIS/Device/ST/STM32H7xx/Include
)
target_compile_options(periph_library PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)
target_compile_definitions(periph_library PRIVATE STM32H723xx)
###############################################################################################################################
############################################################################################################################
############################################# 5. Scheduler Subsystem 
file(GLOB_RECURSE SCHEDULER_SOURCES CONFIGURE_DEPENDS "scheduler/*.c")
add_library(scheduler_library STATIC ${SCHEDULER_SOURCES})
target_include_directories(scheduler_library PUBLIC 
headers
STM32H7/CMSIS/Include
STM32H7/CMSIS/Device/ST/STM32H7xx/Include
)
target_link_libraries(scheduler_library PUBLIC 
clock_library
UNITTEST_library
)
target_compile_definitions(scheduler_library PRIVATE STM32H723xx)
target_compile_options(scheduler_library PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)
#############################################################################################################################
############################################# UNIT TEST  
file(GLOB_RECURSE UNITTEST_SOURCES CONFIGURE_DEPENDS "HIL_UNIT_TEST/*.c")
add_library(UNITTEST_library STATIC ${UNITTEST_SOURCES})
target_include_directories(UNITTEST_library PUBLIC 
headers
STM32H7/CMSIS/Include
STM32H7/CMSIS/Device/ST/STM32H7xx/Include
)
target_link_libraries(UNITTEST_library PUBLIC 
clock_library
scheduler_library
)
target_compile_definitions(UNITTEST_library PRIVATE STM32H723xx)
target_compile_options(UNITTEST_library PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)
#############################################################################################################################
#################################### 6. Sensors Subsystem (RESTORED)
# file(GLOB_RECURSE SENSORS_SOURCES CONFIGURE_DEPENDS "sensors/*.c")
# add_library(sensors_subsystem STATIC ${SENSORS_SOURCES})
# target_include_directories(sensors_subsystem PUBLIC 
#sensors
#scheduler
#headers
#Drivers/CMSIS/Include
#Drivers/CMSIS/Device/ST/STM32H7xx/Include
#)
#target_compile_options(sensors_subsystem PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)
#target_compile_definitions(sensors_subsystem PRIVATE STM32H723xx)
###############################################################################################################################
############################################################################################################################
# ========================================================================== #
# MAIN EXECUTABLE CONFIGURATION
# ========================================================================== #

# 7. Collect Main Application Sources
file(GLOB_RECURSE MAIN_SOURCES "src/*.c" "src/*.s")

# 8. Create the final firmware executable 
add_executable(${PROJECT_NAME}.elf ${MAIN_SOURCES})

# 9. Globally tell the CMSIS headers you are compiling for the STM32H723
target_compile_definitions(${PROJECT_NAME}.elf PRIVATE STM32H723xx)

# Apply architecture and compiler options safely to the executable
target_compile_options(${PROJECT_NAME}.elf PRIVATE ${ARCH_FLAGS} -Wall -Wextra -O2 -std=c11)

# 10. Link options (Safely handles spaces in paths and keeps nosys.specs isolated)
target_link_options(${PROJECT_NAME}.elf PRIVATE 
    ${ARCH_FLAGS} 
    "--specs=nosys.specs" 
    "-T${CMAKE_SOURCE_DIR}/Linker/stm32h723xx_flash.ld"
)

# 11. Link All Compiled Subsystems 
target_link_libraries(${PROJECT_NAME}.elf PRIVATE
    # dsp_subsystem
    periph_library
    scheduler_library
    UNITTEST_library
    clock_library
    # sensors_subsystem
)

# 12. Expose Header-Only Folders 
target_include_directories(${PROJECT_NAME}.elf PRIVATE
    headers
    Drivers/CMSIS/Include
    Drivers/CMSIS/Device/ST/STM32H7xx/Include
)
##############################################################################################################################
# ========================================================================== #
# POST-BUILD FIRMWARE GENERATION 
# ========================================================================== #
add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
    COMMAND arm-none-eabi-objcopy -O binary ${PROJECT_NAME}.elf "${CMAKE_SOURCE_DIR}/${PROJECT_NAME}.bin"
    COMMENT "Generating flashable binary image at project root: ${PROJECT_NAME}.bin"
)
