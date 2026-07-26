
def battery_percentage(voltage):

    min_voltage = 9.0
    max_voltage = 12.6

    percentage = (
        (voltage - min_voltage)
        /
        (max_voltage - min_voltage)
    ) * 100

    percentage = max(
        0,
        min(100, percentage)
    )

    return round(percentage, 2)


if __name__ == "__main__":

    voltage = 11.4

    print(
        "Battery:",
        battery_percentage(voltage),
        "%"
    )

#