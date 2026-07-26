#pragma once

#include <stdio.h>
#include <string.h>

#define HAL_DANGER(mod, x, ...) \
    do { \
        fprintf(stderr, "[%s] \033[31m", (mod)); \
        fprintf(stderr, (x), ##__VA_ARGS__); \
        fprintf(stderr, "\033[0m"); \
    } while (0)

#define HAL_ERROR(mod, x, ...) \
    do { \
        fprintf(stderr, "[%s] \033[31m", (mod)); \
        fprintf(stderr, (x), ##__VA_ARGS__); \
        fprintf(stderr, "\033[0m"); \
        return EXIT_FAILURE; \
    } while (0)

#define HAL_INFO(mod, x, ...) \
    do { \
        fprintf(stderr, "[%s] ", (mod)); \
        fprintf(stderr, (x), ##__VA_ARGS__); \
    } while (0)

#define HAL_WARNING(mod, x, ...) \
    do { \
        fprintf(stderr, "[%s] \033[33m", (mod)); \
        fprintf(stderr, (x), ##__VA_ARGS__); \
        fprintf(stderr, "\033[0m"); \
    } while (0)

#ifndef ALIGN_BACK
#define ALIGN_BACK(x, a) (((x) / (a)) * (a))
#endif
#ifndef ALIGN_UP
#define ALIGN_UP(x, a) ((((x) + ((a)-1)) / a) * a)
#endif
#ifndef CEILING
#define CEILING_POS(x) ((x - (int)(x)) > 0 ? (int)(x + 1) : (int)(x))
#define CEILING_NEG(x) (int)(x)
#define CEILING(x) (((x) > 0) ? CEILING_POS(x) : CEILING_NEG(x))
#endif
#ifndef CEILING_2_POWER
#define CEILING_2_POWER(x, a) (((x) + ((a)-1)) & (~((a) - 1)))
#endif
#ifndef MIN
#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#endif
#ifndef MAX
#define MAX(a, b) (((a) > (b)) ? (a) : (b))
#endif

#define CONTAINS(a, b) strstr(a, b)
#define EMPTY(x) (x[0] == '\0')
#define ENDS_WITH(a, b) \
    ((strlen(a) > strlen(b)) && !strcmp(a + strlen(a) - strlen(b), b))
#define EQUALS(a, b) !strcmp(a, b)
#define EQUALS_CASE(a, b) !strcasecmp(a, b)
#define STARTS_WITH(a, b) !strncmp(a, b, strlen(b))
