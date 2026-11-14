// Shared by the real Windows hook and synthetic packet-entry tests.
static bool ClaimCommand(Command* c,DWORD pid,DWORD thread) {
    return c->magic==0x4c435549 && c->version==2 && IsKnownNativeOpcode(c->opcode) &&
           c->pid==pid && c->thread==thread && InterlockedCompareExchange(&c->state,2,1)==1;
}
