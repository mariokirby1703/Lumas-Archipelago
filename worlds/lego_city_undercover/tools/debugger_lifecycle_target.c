/* Isolated heartbeat process; contains no game or save access. */
#include <windows.h>
#include <stdio.h>
int main(void) {
    for (unsigned i=0;i<400;i++) {
        printf("tick %u\n",i);fflush(stdout);Sleep(50);
    }
    return 0;
}
