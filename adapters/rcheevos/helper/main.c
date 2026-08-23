#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rc_hash.h"
#include "rc_version.h"

#define HELPER_VERSION "0.1.0"

static void print_usage(FILE* stream)
{
    fprintf(
        stream,
        "usage:\n"
        "  rom-metadata-rcheevos --version\n"
        "  rom-metadata-rcheevos hash --console-id <id> --json <path>\n"
    );
}

static void hash_error_message(
    const char* message,
    const struct rc_hash_iterator* iterator
)
{
    (void)iterator;

    if (message != NULL)
        fprintf(stderr, "rcheevos: %s\n", message);
}

static int parse_console_id(const char* text, uint32_t* console_id)
{
    char* end = NULL;
    unsigned long value;

    if (text == NULL || *text == '\0')
        return 0;

    errno = 0;
    value = strtoul(text, &end, 10);

    if (
        errno != 0 ||
        end == text ||
        *end != '\0' ||
        value > UINT32_MAX
    ) {
        return 0;
    }

    *console_id = (uint32_t)value;
    return 1;
}

static int verify_input_readable(const char* path)
{
    FILE* stream = fopen(path, "rb");

    if (stream == NULL)
        return 0;

    fclose(stream);
    return 1;
}

static int run_hash(uint32_t console_id, const char* path)
{
    rc_hash_iterator_t iterator;
    char hash[33];
    int result;

    if (!verify_input_readable(path)) {
        fprintf(stderr, "unable to open input file\n");
        return 3;
    }

    memset(&iterator, 0, sizeof(iterator));
    memset(hash, 0, sizeof(hash));

    rc_hash_initialize_iterator(
        &iterator,
        path,
        NULL,
        0
    );

    iterator.callbacks.error_message = hash_error_message;

    result = rc_hash_generate(
        hash,
        console_id,
        &iterator
    );

    rc_hash_destroy_iterator(&iterator);

    if (!result) {
        fprintf(
            stderr,
            "rcheevos could not generate an identifier for console %u\n",
            console_id
        );
        return 4;
    }

    printf(
        "{"
        "\"schema_version\":1,"
        "\"console_id\":%u,"
        "\"hash\":\"%s\","
        "\"backend\":\"rcheevos\","
        "\"backend_version\":\"%s\""
        "}\n",
        console_id,
        hash,
        rc_version_string()
    );

    return 0;
}

int main(int argc, char** argv)
{
    uint32_t console_id;

    if (
        argc == 2 &&
        strcmp(argv[1], "--version") == 0
    ) {
        printf(
            "rom-metadata-rcheevos %s rcheevos %s\n",
            HELPER_VERSION,
            rc_version_string()
        );
        return 0;
    }

    if (
        argc == 6 &&
        strcmp(argv[1], "hash") == 0 &&
        strcmp(argv[2], "--console-id") == 0 &&
        strcmp(argv[4], "--json") == 0
    ) {
        if (!parse_console_id(argv[3], &console_id)) {
            fprintf(stderr, "invalid console ID\n");
            return 2;
        }

        return run_hash(console_id, argv[5]);
    }

    print_usage(stderr);
    return 2;
}
