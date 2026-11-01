/*
 * checker — mühür doğrulayıcı (tersine mühendislik alıştırması)
 *
 * Mührü kendi içinde taşımaz: /home/player11/lib/blob dosyasını okur,
 * tek baytlık XOR ile çözer ve argv[1] ile karşılaştırır.
 *
 * Amaç: "gizleme" ile "şifreleme" arasındaki farkı göstermek. Baytlar
 * tersine mühendislik araçlarına karşı hiçbir şey korumaz:
 *
 *   strings checker            → mühür görünmez
 *   objdump -d checker         → xor $0x5a görünür
 *   ltrace -e strcmp ./checker → karşılaştırmadaki düz metin görünür
 *   gdb + break strcmp         → aynı sonuç
 *
 * -O0 -fno-builtin ile derlenir; strcmp gerçekten PLT üzerinden çağrılır,
 * böylece ltrace yakalayabilir.
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BLOB_PATH "/home/player11/lib/blob"
#define KEY 0x5a
#define MAX_SEAL 128

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "kullanım: %s <mühür>\n", argv[0]);
        return 2;
    }

    int fd = open(BLOB_PATH, O_RDONLY);
    if (fd < 0) {
        perror("checker");
        return 3;
    }

    unsigned char buffer[MAX_SEAL];
    ssize_t count = read(fd, buffer, sizeof buffer - 1);
    close(fd);
    if (count <= 0) {
        fprintf(stderr, "checker: blob okunamadı\n");
        return 3;
    }
    buffer[count] = '\0';

    for (ssize_t i = 0; i < count; i++) {
        buffer[i] ^= KEY;
    }
    char *seal = (char *)buffer;
    seal[strcspn(seal, "\r\n")] = '\0';

    if (strcmp(seal, argv[1]) == 0) {
        puts("access granted");
        return 0;
    }
    puts("access denied");
    return 1;
}
