SRCS=$(wildcard *.c)
CPPSRCS=$(wildcard *.cpp)
OBJS=$(SRCS:.c=.o) $(CPPSRCS:.cpp=.o)
CFLAGS= -std=c11 -lbsg_manycore_runtime
CPPFLAGS= -std=c++11 -lbsg_manycore_runtime

default: all
all: $(OBJS)
	g++ $^ $(CPPFLAGS) -o host

%.o: %.c
	gcc $(CFLAGS) -c -o $@ $<

%.o: %.cpp
	g++ $(CPPFLAGS) -c -o $@ $<

clean:
	rm -f *.o host

