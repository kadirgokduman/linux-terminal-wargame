/*
 * wargame-read — SUID mühür okuyucusu
 *
 * Sahibi, hedef seviyenin oyuncusudur (ör. player03) ve modu 4755'tir.
 * Bu dosya, SUID bulmacalarının güvenlik sözleşmesidir:
 *
 *   1. Yalnızca /etc/wargame/pass/NN biçimindeki yolları kabul eder.
 *   2. Yolu realpath ile çözer; symlink ile dışarı çıkılamaz.
 *   3. Mühür, okuyucunun sahibine ait olmalıdır (başka seviyeyi okuyamaz).
 *   4. Argümandan gelen hiçbir şey exec/eval edilmez; ortam değişkeni okunmaz.
 *
 * Değiştirirken: O_NOFOLLOW ve sahiplik kontrolünü kaldırmayın. Bu program
 * root olmayan bir kullanıcı adına ayrıcalık taşır.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define PASS_DIR "/etc/wargame/pass/"
#define PASS_DIR_LEN (sizeof(PASS_DIR) - 1)

static void die(const char *message)
{
    fprintf(stderr, "wargame-read: %s\n", message);
    exit(1);
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        die("kullanım: wargame-read <mühür-yolu>  (ör. /etc/wargame/pass/03)");
    }

    char resolved[PATH_MAX];
    if (realpath(argv[1], resolved) == NULL) {
        die("mühür bulunamadı");
    }
    if (strncmp(resolved, PASS_DIR, PASS_DIR_LEN) != 0) {
        die("bu mühür okuyucunun kapsamı dışında");
    }

    const char *seal = resolved + PASS_DIR_LEN;
    if (strlen(seal) != 2 ||
        seal[0] < '0' || seal[0] > '9' ||
        seal[1] < '0' || seal[1] > '9') {
        die("geçersiz mühür adı");
    }

    struct stat st;
    if (stat(resolved, &st) != 0) {
        die("mühür durumu okunamadı");
    }
    if (!S_ISREG(st.st_mode)) {
        die("mühür normal dosya değil");
    }
    if (st.st_uid != geteuid()) {
        die("bu mühür bu okuyucuya ait değil");
    }

    int fd = open(resolved, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) {
        die("mühür açılamadı");
    }

    char buffer[4096];
    ssize_t count;
    while ((count = read(fd, buffer, sizeof buffer)) > 0) {
        if (write(STDOUT_FILENO, buffer, (size_t)count) != count) {
            break;
        }
    }
    close(fd);
    return 0;
}
