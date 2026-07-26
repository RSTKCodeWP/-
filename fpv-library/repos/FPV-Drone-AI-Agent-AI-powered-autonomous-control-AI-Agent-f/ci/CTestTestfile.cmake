# CMake generated Testfile for 
# Source directory: D:/DroneAI/nanohawk-agent
# Build directory: D:/DroneAI/nanohawk-agent/build/ci
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test([=[nanohawk_unit_pipeline]=] "D:/DroneAI/nanohawk-agent/build/ci/nanohawk_unit_tests.exe")
set_tests_properties([=[nanohawk_unit_pipeline]=] PROPERTIES  _BACKTRACE_TRIPLES "D:/DroneAI/nanohawk-agent/CMakeLists.txt;148;add_test;D:/DroneAI/nanohawk-agent/CMakeLists.txt;0;")
add_test([=[nanohawk_transport_checks]=] "D:/DroneAI/nanohawk-agent/build/ci/nanohawk_transport_tests.exe")
set_tests_properties([=[nanohawk_transport_checks]=] PROPERTIES  _BACKTRACE_TRIPLES "D:/DroneAI/nanohawk-agent/CMakeLists.txt;152;add_test;D:/DroneAI/nanohawk-agent/CMakeLists.txt;0;")
add_test([=[nanohawk_config_wiring]=] "D:/DroneAI/nanohawk-agent/build/ci/nanohawk_config_tests.exe")
set_tests_properties([=[nanohawk_config_wiring]=] PROPERTIES  _BACKTRACE_TRIPLES "D:/DroneAI/nanohawk-agent/CMakeLists.txt;156;add_test;D:/DroneAI/nanohawk-agent/CMakeLists.txt;0;")
add_test([=[nanohawk_device_detection]=] "D:/DroneAI/nanohawk-agent/build/ci/nanohawk_device_detection.exe")
set_tests_properties([=[nanohawk_device_detection]=] PROPERTIES  _BACKTRACE_TRIPLES "D:/DroneAI/nanohawk-agent/CMakeLists.txt;160;add_test;D:/DroneAI/nanohawk-agent/CMakeLists.txt;0;")
