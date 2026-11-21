#ifndef DM_BUZZER_PROTOCOL_H
#define DM_BUZZER_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define DM_COMMAND_TIMEOUT_MS 2000u
#define DM_COMMAND_MAX 160u

typedef struct {
    void (*set_active)(void *context, bool active);
    void (*reply)(void *context, const char *line);
    void *context;
} dm_buzzer_io_t;

typedef struct {
    bool active;
    uint32_t last_command_ms;
    size_t used;
    unsigned drop_reason;
    char line[DM_COMMAND_MAX + 1];
} dm_buzzer_t;

void dm_buzzer_init(dm_buzzer_t *state, const dm_buzzer_io_t *io);
void dm_buzzer_poll(dm_buzzer_t *state, uint32_t now_ms, const dm_buzzer_io_t *io);
void dm_buzzer_feed(dm_buzzer_t *state, uint8_t byte, uint32_t now_ms,
                    const dm_buzzer_io_t *io);
void dm_buzzer_uart_fault(dm_buzzer_t *state, const dm_buzzer_io_t *io);

#endif
