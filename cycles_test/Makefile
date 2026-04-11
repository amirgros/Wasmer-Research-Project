.PHONY: all run clean

WASMER_HOME ?= ~/.wasmer
CXX = g++
CXXFLAGS = -std=c++17 -g
INCLUDES = -I$(WASMER_HOME)/include -I.
LIBS = -L$(WASMER_HOME)/lib -lwasmer

TARGET = sum_test
SRC = sum_test.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	@mkdir -p build
	$(CXX) -o $(TARGET) $(SRC) $(INCLUDES) $(LIBS) $(CXXFLAGS)
	@echo "✓ Built $(TARGET)"

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build $(TARGET)
	@echo "✓ Cleaned"

help:
	@echo "Usage:"
	@echo "  make        - Build sum_test"
	@echo "  make run    - Build and run sum_test"
	@echo "  make clean  - Remove build artifacts"
