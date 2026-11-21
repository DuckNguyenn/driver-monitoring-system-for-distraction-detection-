#include "buzzer_protocol.h"

#include <string.h>

enum { DROP_NONE, DROP_LONG, DROP_INVALID, DROP_UART };

static void set_active(dm_buzzer_t *state, bool active, const dm_buzzer_io_t *io)
{
    if (state->active != active) {
        state->active = active;
        io->set_active(io->context, active);
    }
}

void dm_buzzer_init(dm_buzzer_t *state, const dm_buzzer_io_t *io)
{
    memset(state, 0, sizeof(*state));
    io->set_active(io->context, false);
}

void dm_buzzer_poll(dm_buzzer_t *state, uint32_t now_ms, const dm_buzzer_io_t *io)
{
    if (state->active && (uint32_t)(now_ms - state->last_command_ms) >= DM_COMMAND_TIMEOUT_MS) {
        set_active(state, false, io);
        io->reply(io->context, "FAULT COMMAND_TIMEOUT");
    }
}

static void command(dm_buzzer_t *state, uint32_t now_ms, const dm_buzzer_io_t *io)
{
    char *start = state->line;
    state->line[state->used] = '\0';
    while (*start == ' ' || *start == '\t') {
        ++start;
    }
    char *end = state->line + state->used;
    while (end > start && (end[-1] == ' ' || end[-1] == '\t')) {
        *--end = '\0';
    }
    if (*start == '\0') {
        return;
    }
    bool active;
    if (strcmp(start, "ALERT 1") == 0 || strncmp(start, "ALERT 1 ", 8) == 0) {
        active = true;
    } else if (strcmp(start, "ALERT 0") == 0) {
        active = false;
    } else {
        io->reply(io->context, "ERR UNKNOWN_COMMAND");
        return;
    }
    state->last_command_ms = now_ms;
    set_active(state, active, io);
    io->reply(io->context, active ? "OK ALERT 1" : "OK ALERT 0");
}

void dm_buzzer_feed(dm_buzzer_t *state, uint8_t byte, uint32_t now_ms,
                    const dm_buzzer_io_t *io)
{
    dm_buzzer_poll(state, now_ms, io);
    if (byte == '\n') {
        if (state->drop_reason == DROP_LONG) {
            io->reply(io->context, "ERR TOO_LONG");
        } else if (state->drop_reason == DROP_INVALID) {
            io->reply(io->context, "ERR UNKNOWN_COMMAND");
        } else if (state->drop_reason == DROP_NONE) {
            command(state, now_ms, io);
        }
        state->used = 0;
        state->drop_reason = DROP_NONE;
    } else if (byte != '\r' && state->drop_reason == DROP_NONE) {
        if ((byte < 32 && byte != '\t') || byte > 126) {
            state->drop_reason = DROP_INVALID;
        } else if (state->used == DM_COMMAND_MAX) {
            state->drop_reason = DROP_LONG;
        } else {
            state->line[state->used++] = (char)byte;
        }
    }
}

void dm_buzzer_uart_fault(dm_buzzer_t *state, const dm_buzzer_io_t *io)
{
    set_active(state, false, io);
    state->used = 0;
    state->drop_reason = DROP_UART;
    io->reply(io->context, "ERR UART_RX");
}
