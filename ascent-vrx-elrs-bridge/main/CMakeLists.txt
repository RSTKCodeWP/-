idf_component_register(
    SRCS
        "main.c"
        "crsf_bridge.c"
        "vrx_proto.c"
        "vrx_udp.c"
        "usb_rndis_net.c"
        "console_cli.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_netif
        esp_event
        nvs_flash
        lwip
        esp_timer
        usb
)
