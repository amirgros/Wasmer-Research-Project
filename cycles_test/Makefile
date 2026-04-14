.PHONY: all run clean help

WASMER_HOME ?= ~/.wasmer
CXX = g++
CXXFLAGS = -std=c++17 -g -fno-omit-frame-pointer
INCLUDES = -I$(WASMER_HOME)/include -I.
LIBS = -L$(WASMER_HOME)/lib -lwasmer

# Find all .cpp files in the current directory
SOURCES = $(wildcard *.cpp)
# Generate executable names by replacing .cpp with nothing
TARGETS = $(SOURCES:.cpp=)

all: $(TARGETS)

# Rule to build each executable from its .cpp file
%: %.cpp
	$(CXX) -o $@ $< $(INCLUDES) $(LIBS) $(CXXFLAGS)
	@echo "✓ Built $@"

run: $(TARGETS)
	@echo "Built executables: $(TARGETS)"
	@echo "Run them individually, e.g., ./sum_test"

clean:
	rm -f $(TARGETS)
	@echo "✓ Cleaned executables"

help:
	@echo "Usage:"
	@echo "  make        - Build all executables from .cpp files"
	@echo "  make run    - Build all and list executables"
	@echo "  make clean  - Remove all built executables"
