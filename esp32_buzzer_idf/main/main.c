#include "board_config.h"
#include "buzzer_protocol.h"

#include <stdint.h>
#include <string.h>
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

static const uart_port_t SERIAL_PORT = UART_NUM_0;

static uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

static void buzzer_output(void *context, bool active)
{
    (void)context;
    int level = active ? DM_BUZZER_ACTIVE_LEVEL : !DM_BUZZER_ACTIVE_LEVEL;
    ESP_ERROR_CHECK(gpio_set_level(DM_BUZZER_GPIO, level));
}

static void serial_reply(void *context, const char *line)
{
    (void)context;
    uart_write_bytes(SERIAL_PORT, line, strlen(line));
    uart_write_bytes(SERIAL_PORT, "\n", 1);
}

static void recover_uart(dm_buzzer_t *state, const dm_buzzer_io_t *io, QueueHandle_t events)
{
    dm_buzzer_uart_fault(state, io);
    uart_flush_input(SERIAL_PORT);
    xQueueReset(events);
}

void app_main(void)
{
    /* Preload OFF before enabling output; R2 also holds Q1 off during reset. */
    ESP_ERROR_CHECK(gpio_set_level(DM_BUZZER_GPIO, !DM_BUZZER_ACTIVE_LEVEL));
    const gpio_config_t output = {
        .pin_bit_mask = 1ULL << DM_BUZZER_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&output));
    const uart_config_t uart = {
        .baud_rate = DM_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_param_config(SERIAL_PORT, &uart));
    ESP_ERROR_CHECK(uart_set_pin(SERIAL_PORT, DM_UART_TX_GPIO, DM_UART_RX_GPIO,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    QueueHandle_t events;
    ESP_ERROR_CHECK(uart_driver_install(SERIAL_PORT, 1024, 0, 20, &events, 0));
    const dm_buzzer_io_t io = { .set_active = buzzer_output, .reply = serial_reply };
    dm_buzzer_t state;
    dm_buzzer_init(&state, &io);

    for (;;) {
        dm_buzzer_poll(&state, now_ms(), &io);
        uart_event_t event;
        if (xQueueReceive(events, &event, pdMS_TO_TICKS(10)) != pdTRUE) {
            continue;
        }
        if (event.type == UART_DATA) {
            size_t remaining = event.size;
            while (remaining > 0) {
                uint8_t bytes[64];
                size_t wanted = remaining < sizeof(bytes) ? remaining : sizeof(bytes);
                int received = uart_read_bytes(SERIAL_PORT, bytes, wanted, 0);
                if (received <= 0) {
                    recover_uart(&state, &io, events);
                    break;
                }
                remaining -= (size_t)received;
                uint32_t timestamp = now_ms();
                for (int index = 0; index < received; ++index) {
                    dm_buzzer_feed(&state, bytes[index], timestamp, &io);
                }
            }
        } else if (event.type == UART_FIFO_OVF || event.type == UART_BUFFER_FULL ||
                   event.type == UART_FRAME_ERR || event.type == UART_PARITY_ERR ||
                   event.type == UART_BREAK) {
            recover_uart(&state, &io, events);
        }
    }
}
