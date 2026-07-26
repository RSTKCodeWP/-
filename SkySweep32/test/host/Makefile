# Host-side unit tests for the protocol parsers.
#
# These compile the real src/protocols/*.cpp sources against a minimal Arduino.h
# stub (this directory) with a desktop compiler + AddressSanitizer. No ESP32
# toolchain or PlatformIO registry is needed, so they run anywhere g++ is present.
#
#   make        # build and run
#   make clean

CXX      ?= g++
SRCDIR    = ../../src/protocols
CXXFLAGS  = -std=gnu++11 -Wall -Wextra -g -O1 \
            -fsanitize=address,undefined -fno-omit-frame-pointer \
            -I. -I$(SRCDIR)

SRCS = test_parsers.cpp $(SRCDIR)/crsf_parser.cpp $(SRCDIR)/mavlink_parser.cpp
BIN  = test_parsers

.PHONY: all test clean
all: test

$(BIN): $(SRCS) Arduino.h
	$(CXX) $(CXXFLAGS) $(SRCS) -o $(BIN)

test: $(BIN)
	./$(BIN)

clean:
	rm -f $(BIN)
