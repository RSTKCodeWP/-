#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sys/select.h>  // For select()
#include <sys/time.h>    // For gettimeofday()
#include <getopt.h>      // For getopt_long()
#include <errno.h>       // For errno and EINTR
#include <math.h>        // For fabs() function to calculate percentage difference
#include <sys/stat.h>    // For checking file existence
#include <unistd.h>      // For unlink (deleting files)

#define CONFIG_FILE "config.cfg"
#define DEFAULT_VERSION "0.1.0"
#define DEFAULT_MISSING_MESSAGE_TIMEOUT 1.5
#define DEFAULT_PAUSE_DURATION 5.0
#define DEFAULT_RSSI_CALL_INTERVAL 6.0
#define DEFAULT_PERCENTAGE_CHANGE 5.0
#define DEFAULT_ANTENNA_VALUE -105      // Default antenna value when missing
#define DEFAULT_UDP_PORT 9999.0         // Default UDP port as double to allow unified handling
#define DEFAULT_FEC_RECOVERY_THRESHOLD 50.0
#define DEFAULT_LOST_PACKAGES_THRESHOLD 5.0

// File paths for recording indicators
#define RECORDING_STARTED_FILE "/tmp/recording_started"
#define RECORDING_STOPPED_FILE "/tmp/recording_stopped"

// Global configuration values, all as double for unified handling
char current_version[16] = DEFAULT_VERSION;
double missing_message_timeout = DEFAULT_MISSING_MESSAGE_TIMEOUT;
double pause_duration = DEFAULT_PAUSE_DURATION;
double rssi_call_interval = DEFAULT_RSSI_CALL_INTERVAL;
double percentage_change_threshold = DEFAULT_PERCENTAGE_CHANGE;
double fec_recovery_threshold = DEFAULT_FEC_RECOVERY_THRESHOLD;
double lost_packages_threshold = DEFAULT_LOST_PACKAGES_THRESHOLD;
double udp_port = DEFAULT_UDP_PORT;

int parse_data = 1;  // Global flag to control data parsing, enabled by default
int verbose = 0;     // Global verbose flag, disabled by default

int last_rssi_quality = -1; // Store last rssi_link_quality, -1 means not set yet
struct timeval last_message_time;  // Time when the last message was received
struct timeval last_rssi_call_time;  // Time when /usr/bin/channels.sh 0 rssi_link_quality was last called
int called_on_timeout = 0;  // Flag to track if /usr/bin/channels.sh 0 1000 was called on timeout
int pause_parsing = 0;  // Flag to indicate whether parsing is paused

// Increment version by patch level
void increment_patch_version(char* version) {
    int major, minor, patch;
    sscanf(version, "%d.%d.%d", &major, &minor, &patch);
    patch++;
    snprintf(current_version, sizeof(current_version), "%d.%d.%d", major, minor, patch);
}

// Function to check if a file exists
int file_exists(const char *filename) {
    struct stat buffer;
    return (stat(filename, &buffer) == 0);
}

// Function to handle file operations for recording
void handle_recording(const char *command) {
    if (strcmp(command, "start_record") == 0) {
        if (file_exists(RECORDING_STOPPED_FILE)) {
            unlink(RECORDING_STOPPED_FILE);  // Delete recording_stopped if exists
            if (verbose) {
                printf("Deleted %s\n", RECORDING_STOPPED_FILE);
            }
        }
        FILE *f = fopen(RECORDING_STARTED_FILE, "w");
        if (f) {
            fclose(f);
            if (verbose) {
                printf("Created %s\n", RECORDING_STARTED_FILE);
            }
        }
    } else if (strcmp(command, "stop_record") == 0) {
        if (file_exists(RECORDING_STARTED_FILE)) {
            unlink(RECORDING_STARTED_FILE);  // Delete recording_started if exists
            if (verbose) {
                printf("Deleted %s\n", RECORDING_STARTED_FILE);
            }
        }
        FILE *f = fopen(RECORDING_STOPPED_FILE, "w");
        if (f) {
            fclose(f);
            if (verbose) {
                printf("Created %s\n", RECORDING_STOPPED_FILE);
            }
        }
    }
}

// Function to write default config file with descriptions if it doesn't exist
void create_default_config_file() {
    FILE *file = fopen(CONFIG_FILE, "w");
    if (file != NULL) {
        fprintf(file, "# Configuration file for UDP Reader program\n");
        fprintf(file, "version=%s\n\n", DEFAULT_VERSION);

        fprintf(file, "# The timeout (in seconds) for detecting missing messages.\n");
        fprintf(file, "# If no message is received within this timeout, /usr/bin/channels.sh 0 1000 will be called.\n");
        fprintf(file, "missing_message_timeout=%.1f\n\n", DEFAULT_MISSING_MESSAGE_TIMEOUT);

        fprintf(file, "# The duration (in seconds) to pause message parsing after /usr/bin/channels.sh 0 1000 is called.\n");
        fprintf(file, "# During this pause, no messages are processed.\n");
        fprintf(file, "pause_duration=%.1f\n\n", DEFAULT_PAUSE_DURATION);

        fprintf(file, "# The minimum time interval (in seconds) between successive calls to /usr/bin/channels.sh 0 rssi_link_quality.\n");
        fprintf(file, "# Even if the RSSI changes significantly, calls will not be made more frequently than this interval.\n");
        fprintf(file, "rssi_call_interval=%.1f\n\n", DEFAULT_RSSI_CALL_INTERVAL);

        fprintf(file, "# The minimum percentage change in rssi_link_quality that triggers a call to /usr/bin/channels.sh 0 rssi_link_quality.\n");
        fprintf(file, "# If the change in RSSI exceeds this percentage, an update will be triggered.\n");
        fprintf(file, "percentage_change=%.1f\n\n", DEFAULT_PERCENTAGE_CHANGE);

        fprintf(file, "# The threshold for FEC recovery. If fec_recovery exceeds this value, /usr/bin/channels.sh 0 1000 will be called.\n");
        fprintf(file, "fec_recovery_threshold=%.1f\n\n", DEFAULT_FEC_RECOVERY_THRESHOLD);

        fprintf(file, "# The threshold for lost packages. If lost_packages exceeds this value, /usr/bin/channels.sh 0 1000 will be called.\n");
        fprintf(file, "lost_packages_threshold=%.1f\n\n", DEFAULT_LOST_PACKAGES_THRESHOLD);

        fprintf(file, "# The UDP port to listen on for incoming data.\n");
        fprintf(file, "udp_port=%.1f\n\n", DEFAULT_UDP_PORT);

        fprintf(file, "# Version History:\n");
        fprintf(file, "# %s: Initial configuration setup with timeouts, pause, and percentage change for RSSI.\n", DEFAULT_VERSION);
        fclose(file);
    }
}

// Function to load configuration from the config file
void load_config() {
    FILE *file = fopen(CONFIG_FILE, "r");
    if (file == NULL) {
        printf("Configuration file not found. Creating default config file...\n");
        create_default_config_file();
    } else {
        char line[256];
        while (fgets(line, sizeof(line), file)) {
            if (sscanf(line, "version=%s", current_version)) {
                continue;
            } else if (sscanf(line, "missing_message_timeout=%lf", &missing_message_timeout)) {
                continue;
            } else if (sscanf(line, "pause_duration=%lf", &pause_duration)) {
                continue;
            } else if (sscanf(line, "rssi_call_interval=%lf", &rssi_call_interval)) {
                continue;
            } else if (sscanf(line, "percentage_change=%lf", &percentage_change_threshold)) {
                continue;
            } else if (sscanf(line, "fec_recovery_threshold=%lf", &fec_recovery_threshold)) {
                continue;
            } else if (sscanf(line, "lost_packages_threshold=%lf", &lost_packages_threshold)) {
                continue;
            } else if (sscanf(line, "udp_port=%lf", &udp_port)) {
                continue;
            }
        }
        fclose(file);
        printf("Configuration loaded from: %s\n", CONFIG_FILE);
    }
}

// Function to append the new version and reason to the version history in config file
void update_version_history(const char* reason) {
    FILE *file = fopen(CONFIG_FILE, "a");
    if (file != NULL) {
        fprintf(file, "# %s: %s\n", current_version, reason);
        fclose(file);
    }
}

// Log a version change with a short description of the change
void log_change(const char* change_description) {
    increment_patch_version(current_version);
    update_version_history(change_description);
}

// Function to call /usr/bin/channels.sh
void call_channels(int rssi_link_quality) {
    char command[128];
    snprintf(command, sizeof(command), "/usr/bin/channels.sh 0 %d", rssi_link_quality);
    if (verbose) {
        printf("Executing: %s\n", command);
    }
    int result = system(command);
    if (result == -1) {
        perror("Command execution failed");
    }
}

// Function to calculate the percentage change
double calculate_percentage_change(int old_value, int new_value) {
    return fabs((double)(new_value - old_value) / old_value) * 100.0;
}

// Function to check if rssi_call_interval (6 seconds by default) has passed since last RSSI call
int can_call_rssi_link_quality() {
    struct timeval current_time;
    gettimeofday(&current_time, NULL);

    double time_diff = (current_time.tv_sec - last_rssi_call_time.tv_sec) +
                       (current_time.tv_usec - last_rssi_call_time.tv_usec) / 1000000.0;
    
    return time_diff >= rssi_call_interval;
}

// Function to pause parsing for a duration specified by pause_duration (default 5 seconds)
void pause_parsing_for_duration() {
    if (verbose) {
        printf("Pausing parsing for %.1f seconds...\n", pause_duration);
    }
    
    int pause_seconds = (int)pause_duration;  // Extract the whole number part of pause_duration
    int pause_microseconds = (pause_duration - pause_seconds) * 1000000;  // Get the fractional part
    
    // Use sleep() for whole seconds
    if (pause_seconds > 0) {
        sleep(pause_seconds);
    }
    
    // Use usleep() for fractional part in microseconds
    if (pause_microseconds > 0) {
        usleep(pause_microseconds);
    }
    
    pause_parsing = 0;  // Reset parsing flag
    
    if (verbose) {
        printf("Resuming parsing after %.1f seconds...\n", pause_duration);
    }
}

void process_command(const char* command) {
    if (strcmp(command, "pause") == 0) {
        if (verbose) {
            printf("Received special command: PAUSE. Stopping data parsing.\n");
        }
        parse_data = 0;
    } else if (strcmp(command, "resume") == 0) {
        if (verbose) {
            printf("Received special command: RESUME. Resuming data parsing.\n");
        }
        parse_data = 1;
    } else if (strcmp(command, "start_record") == 0 || strcmp(command, "stop_record") == 0) {
        handle_recording(command);
    } else {
        if (verbose) {
            printf("Executing command: %s\n", command);
        }
        int result = system(command);
        if (result == -1) {
            perror("Command execution failed");
        }
    }
}

void process_message(const char* message) {
    if (pause_parsing) {
        // Skip parsing if we are in the pause window
        return;
    }

    // Check if the message begins with "special"
    if (strncmp(message, "special:", 8) == 0) {
        char* token = strtok((char*)message, ":");
        token = strtok(NULL, ":");  // Move to next token ("run_command" or "pause" or "resume")
        
        if (token != NULL) {
            char* command_to_run = strtok(NULL, ":");
            if (strcmp(token, "run_command") == 0 && command_to_run != NULL) {
                process_command(command_to_run);
            } else if (strcmp(token, "pause") == 0 || strcmp(token, "resume") == 0 ||
                       strcmp(token, "start_record") == 0 || strcmp(token, "stop_record") == 0) {
                process_command(token);
            } else {
                printf("Error: Unsupported special command\n");
            }
        } else {
            printf("Error: Missing special command\n");
        }
        return;
    }

    if (!parse_data) {
        // If parsing is paused, ignore regular messages
        if (verbose) {
            printf("Data parsing is paused. Ignoring message: %s\n", message);
        }
        return;
    }

    // Expected format: timestamp:rssi_link_quality:snr_link_quality:fec_recovery:lost_packages:best_antenna0:best_antenna1:best_antenna2:best_antenna3
    char* token;
    char* message_copy = strdup(message);  // Create a copy of the message to work with
    int field_count = 0;  // To track how many fields we successfully parse

    // Parse timestamp
    token = strtok(message_copy, ":");
    if (token == NULL) {
        printf("Error: Missing timestamp\n");
        free(message_copy);
        return;
    }
    long timestamp = atol(token);
    field_count++;

    // Parse rssi_link_quality
    token = strtok(NULL, ":");
    if (token == NULL) {
        printf("Error: Missing RSSI Link Quality\n");
        free(message_copy);
        return;
    }
    int rssi_link_quality = atoi(token);
    field_count++;

    // Parse snr_link_quality
    token = strtok(NULL, ":");
    if (token == NULL) {
        printf("Error: Missing SNR Link Quality\n");
        free(message_copy);
        return;
    }
    int snr_link_quality = atoi(token);
    field_count++;

    // Parse fec_recovery
    token = strtok(NULL, ":");
    if (token == NULL) {
        printf("Error: Missing FEC Recovery\n");
        free(message_copy);
        return;
    }
    int fec_recovery = atoi(token);
    field_count++;

    // Parse lost_packages
    token = strtok(NULL, ":");
    if (token == NULL) {
        printf("Error: Missing Lost Packages\n");
        free(message_copy);
        return;
    }
    int lost_packages = atoi(token);
    field_count++;

    // Check if fec_recovery > fec_recovery_threshold or lost_packages > lost_packages_threshold
    if (fec_recovery > fec_recovery_threshold || lost_packages > lost_packages_threshold) {
        // Call /usr/bin/channels.sh 0 1000 and pause for the duration specified in the config
        call_channels(1000);
        last_rssi_quality = 1000;  // Set rssi_link_quality to 1000
        pause_parsing_for_duration();
    }

    // Parse best_antenna values (optional: continue normal parsing after 5 seconds)
    int antennas[4] = {DEFAULT_ANTENNA_VALUE, DEFAULT_ANTENNA_VALUE, DEFAULT_ANTENNA_VALUE, DEFAULT_ANTENNA_VALUE};  // Initialize antenna values to -105
    for (int i = 0; i < 4; i++) {
        token = strtok(NULL, ":");
        if (token == NULL) {
            if (verbose) {
                printf("Warning: Missing Antenna %d value, using default: %d\n", i, DEFAULT_ANTENNA_VALUE);
            }
        } else {
            antennas[i] = atoi(token);
            field_count++;
        }
    }

    // Update the last message time and reset timeout flag
    gettimeofday(&last_message_time, NULL);

    if (called_on_timeout) {
        // If the message resumes after the timeout, trigger /usr/bin/channels.sh 0 rssi_link_quality
        if (can_call_rssi_link_quality()) {
            call_channels(rssi_link_quality);
            gettimeofday(&last_rssi_call_time, NULL);  // Update the last call time
        }
        called_on_timeout = 0;  // Reset the flag after calling
    }

    // Check if rssi_link_quality changed by more than percentage_change_threshold and can call
    if (last_rssi_quality >= 0 && can_call_rssi_link_quality()) {
        double percentage_change = calculate_percentage_change(last_rssi_quality, rssi_link_quality);
        if (percentage_change > percentage_change_threshold) {
            call_channels(rssi_link_quality);  // Call the command
            gettimeofday(&last_rssi_call_time, NULL);  // Update the last call time
            last_rssi_quality = rssi_link_quality;  // Update the last value
        }
    } else if (last_rssi_quality == -1) {
        // First time calling channels.sh
        call_channels(rssi_link_quality);
        gettimeofday(&last_rssi_call_time, NULL);  // Update the last call time
        last_rssi_quality = rssi_link_quality;
    }

    // Free the duplicated message
    free(message_copy);
}

int main(int argc, char* argv[]) {
    int opt;
    
    // Option parsing
    static struct option long_options[] = {
        {"udp-port", required_argument, 0, 'p'},
        {"verbose", no_argument, &verbose, 1},
        {0, 0, 0, 0}
    };

    while ((opt = getopt_long(argc, argv, "p:", long_options, NULL)) != -1) {
        switch (opt) {
            case 'p':
                udp_port = atof(optarg);  // Use atof to handle both integer and floating-point arguments
                if (verbose) {
                    printf("Using UDP port: %.1f\n", udp_port);
                }
                break;
            case 0:
                // If this option sets a flag (verbose), do nothing
                break;
            default:
                fprintf(stderr, "Usage: %s [--udp-port port] [--verbose]\n", argv[0]);
                exit(EXIT_FAILURE);
        }
    }

    // Load configuration from config.cfg or create it with default values
    load_config();

    // Increment version patch and update the config file
    log_change("Unified handling of all numeric values in config file as doubles.");

    int sockfd;
    struct sockaddr_in server_addr;
    char buffer[1024];
    socklen_t addr_len = sizeof(server_addr);

    // Create UDP socket
    if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("socket creation failed");
        exit(EXIT_FAILURE);
    }

    memset(&server_addr, 0, sizeof(server_addr));

    // Fill server information
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons((int)udp_port);  // Use udp_port from config, casted to int
    server_addr.sin_addr.s_addr = INADDR_ANY;

    // Bind the socket
    if (bind(sockfd, (const struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("bind failed");
        exit(EXIT_FAILURE);
    }

    fd_set readfds;  // Set of file descriptors to monitor for input
    struct timeval timeout;  // Timeout for select()
    struct timeval current_time;  // To track the current time

    // Initialize the time for last RSSI call to prevent immediate first call
    gettimeofday(&last_rssi_call_time, NULL);

    while (1) {
        // Initialize the set of file descriptors
        FD_ZERO(&readfds);
        FD_SET(sockfd, &readfds);

        // Set timeout for missing message detection from the config file
        timeout.tv_sec = (int)missing_message_timeout;
        timeout.tv_usec = (int)((missing_message_timeout - timeout.tv_sec) * 1000000);  // Fractional part in microseconds

        // Use select to wait for data on the socket
        int activity = select(sockfd + 1, &readfds, NULL, NULL, &timeout);

        if (activity < 0 && errno != EINTR) {
            perror("select error");
        }

        if (activity > 0 && FD_ISSET(sockfd, &readfds)) {
            // Data is available to read from the socket
            int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr *)&server_addr, &addr_len);

            if (n > 4) {
                // Read the first 4 bytes for the message size
                uint32_t message_size;
                memcpy(&message_size, buffer, 4);
                message_size = ntohl(message_size);  // Convert from network byte order

                if (message_size > 0 && message_size <= (n - 4)) {
                    // Extract the message
                    char message[message_size + 1];
                    memcpy(message, buffer + 4, message_size);
                    message[message_size] = '\0';  // Null-terminate the string

                    // Print the message if verbose is enabled
                    if (verbose) {
                        printf("Received Message: %s\n", message);
                    }

                    // Process the message to extract and analyze data or execute a command
                    process_message(message);
                }
            }
        } else {
            // Timeout occurred, check if no messages have been received
            gettimeofday(&current_time, NULL);
            double time_diff = (current_time.tv_sec - last_message_time.tv_sec) +
                               (current_time.tv_usec - last_message_time.tv_usec) / 1000000.0;

            if (time_diff >= missing_message_timeout && parse_data == 1 && called_on_timeout == 0) {
                // No message received within the timeout period, call channels.sh with argument 1000
                call_channels(1000);
                last_rssi_quality = 1000;  // Set rssi_link_quality to 1000
                pause_parsing_for_duration();  // Pause parsing after this call
                called_on_timeout = 1;  // Set the flag to indicate the command was called
            }

            if (verbose) {
                printf("Waiting for data...\n");
            }
        }
    }

    close(sockfd);
    return 0;
}
