/* Serialize seek resets against complete decode/output iterations. The two
 * locks are separate: decoding may wait for the output queue to drain.
 * The seek hold interrupts those waits before acquiring either lock. */
#include <stdatomic.h>
#include <libavutil/time.h>

static pthread_mutex_t s_audio_decode_mx = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t s_audio_output_mx = PTHREAD_MUTEX_INITIALIZER;
static atomic_int s_audio_seek_hold;

int evo_audio_seek_begin(void)
{
    atomic_store(&s_audio_seek_hold, 1);
    const int64_t deadline = av_gettime_relative() + 2000000;
    do {
        if (pthread_mutex_trylock(&s_audio_decode_mx) == 0) {
            if (pthread_mutex_trylock(&s_audio_output_mx) == 0)
                return 1;
            pthread_mutex_unlock(&s_audio_decode_mx);
        }
        usleep(1000);
    } while (av_gettime_relative() < deadline);
    /* No reset is safe if either worker is still using the old epoch. */
    atomic_store(&s_audio_seek_hold, 0);
    return 0;
}

void evo_audio_seek_end(void)
{
    pthread_mutex_unlock(&s_audio_output_mx);
    pthread_mutex_unlock(&s_audio_decode_mx);
    atomic_store(&s_audio_seek_hold, 0);
}
