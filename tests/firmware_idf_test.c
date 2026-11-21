#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "buzzer_protocol.h"

typedef struct {
    bool high;
    unsigned count;
    char last[64];
} fake_io_t;

static fake_io_t output;
static dm_buzzer_t state;

static void set_active(void *context, bool active)
{
    ((fake_io_t *)context)->high = active;
}

static void reply(void *context, const char *line)
{
    fake_io_t *out = context;
    ++out->count;
    assert(strlen(line) < sizeof(out->last));
    strcpy(out->last, line);
}

static const dm_buzzer_io_t io = { set_active, reply, &output };

static void reset(void)
{
    memset(&output, 0, sizeof(output));
    output.high = true;
    dm_buzzer_init(&state, &io);
    assert(!output.high && !state.active && output.count == 0);
}

static void feed(const char *text, uint32_t timestamp)
{
    while (*text != '\0') {
        dm_buzzer_feed(&state, (uint8_t)*text++, timestamp, &io);
    }
}

static void framing_and_commands(void)
{
    reset();
    feed("ALERT 1", 0);
    assert(!output.high && output.count == 0);
    feed(" eyes_closed_too_long\r\nALERT 0\n", 1);
    assert(!output.high && output.count == 2);
    assert(strcmp(output.last, "OK ALERT 0") == 0);
    feed("\t ALERT 1 \t\r\n", 2);
    assert(output.high && strcmp(output.last, "OK ALERT 1") == 0);
    const char *invalid[] = {"ALERT 10\n", "ALERT 0 reason\n", "ALERT 1x\n"};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        feed(invalid[i], 100);
        assert(strcmp(output.last, "ERR UNKNOWN_COMMAND") == 0);
        assert(state.last_command_ms == 2);
    }
    unsigned replies = output.count;
    feed(" \t\r\n", 1000);
    assert(output.count == replies && state.last_command_ms == 2);
    dm_buzzer_poll(&state, 2002, &io);
    assert(!output.high && strcmp(output.last, "FAULT COMMAND_TIMEOUT") == 0);
}

static void watchdog_and_rollover(void)
{
    reset();
    feed("ALERT 1\n", 0);
    for (unsigned i = 1; i <= 8; ++i) {
        feed("ALERT 1\n", i * 500);
        assert(output.high);
    }
    dm_buzzer_poll(&state, 5999, &io);
    assert(output.high);
    dm_buzzer_poll(&state, 6000, &io);
    assert(!output.high && strcmp(output.last, "FAULT COMMAND_TIMEOUT") == 0);
    unsigned replies = output.count;
    dm_buzzer_poll(&state, 9000, &io);
    assert(output.count == replies);
    uint32_t start = UINT32_MAX - 1000u;
    feed("ALERT 1\n", start);
    dm_buzzer_poll(&state, start + 1999u, &io);
    assert(output.high);
    dm_buzzer_poll(&state, start + 2000u, &io);
    assert(!output.high);
}

static void invalid_and_oversized_lines(void)
{
    reset();
    feed("ALERT 1 ", 0);
    for (unsigned i = 8; i < DM_COMMAND_MAX; ++i) {
        dm_buzzer_feed(&state, 'x', 0, &io);
    }
    feed("\n", 0);
    assert(output.high && strcmp(output.last, "OK ALERT 1") == 0);
    feed("ALERT 0\n", 0);
    feed("ALERT 1 ", 1);
    for (unsigned i = 8; i <= DM_COMMAND_MAX; ++i) {
        dm_buzzer_feed(&state, 'x', 1, &io);
    }
    feed("\n", 1);
    assert(!output.high && strcmp(output.last, "ERR TOO_LONG") == 0);
    feed("ALERT 1", 2);
    dm_buzzer_feed(&state, 0, 2, &io);
    feed("\n", 2);
    assert(!output.high && strcmp(output.last, "ERR UNKNOWN_COMMAND") == 0);
    feed("ALERT 1\n", 100);
    for (unsigned i = 1; i <= 250; ++i) {
        dm_buzzer_feed(&state, 'x', 100 + i * 8, &io);
    }
    assert(!output.high && strcmp(output.last, "FAULT COMMAND_TIMEOUT") == 0);
    feed("\n", 2101);
    assert(strcmp(output.last, "ERR TOO_LONG") == 0);
}

static void uart_fault_discards_partial_command(void)
{
    reset();
    feed("ALERT 1\nALERT ", 0);
    dm_buzzer_uart_fault(&state, &io);
    assert(!output.high && strcmp(output.last, "ERR UART_RX") == 0);
    feed("1\n", 1);
    assert(!output.high && strcmp(output.last, "ERR UART_RX") == 0);
    feed("ALERT 1\n", 2);
    assert(output.high && strcmp(output.last, "OK ALERT 1") == 0);
}

int main(void)
{
    framing_and_commands();
    watchdog_and_rollover();
    invalid_and_oversized_lines();
    uart_fault_discards_partial_command();
    puts("ESP-IDF protocol: PASS (framing, ACK, watchdog, rollover, overflow, UART fault)");
    return 0;
}
