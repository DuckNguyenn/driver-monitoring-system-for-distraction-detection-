#ifndef DM_BOARD_CONFIG_H
#define DM_BOARD_CONFIG_H

/* ESP32_WROOM32_NATIVE: U1 pad 10 -> R1 -> Q1 (BC337). */
#define DM_BUZZER_GPIO 25
#define DM_BUZZER_ACTIVE_LEVEL 1
/* UART0 through an external USB-to-UART bridge; J2 pins 1/2. */
#define DM_UART_TX_GPIO 1
#define DM_UART_RX_GPIO 3
#define DM_UART_BAUD 115200

#endif
