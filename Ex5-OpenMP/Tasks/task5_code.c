#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

int main(void) {
    const size_t n = 1000000000ULL;  // 1e9
    double *data = malloc(n * sizeof *data);
    if (!data) {
        fprintf(stderr, "Error: malloc failed\n");
        return 1;
    }

    double start = omp_get_wtime();

    double sum    = 0.0;
    double sum_sq = 0.0;

    #pragma omp parallel
    {
        // LOOP 1: initialize data
        // We DO NOT use nowait here, because the next loop reads data[].
        #pragma omp for
        for (size_t i = 0; i < n; ++i) {
            data[i] = (double)(i % 10);
        }

        #pragma omp barrier

        // LOOP 2: compute sum over reversed array, with reduction and nowait
        #pragma omp for reduction(+:sum) nowait
        for (size_t i = 0; i < n; ++i) {
            sum += data[n - 1 - i];
        }

        // LOOP 3: compute sum of squares, with reduction and nowait
        #pragma omp for reduction(+:sum_sq) nowait
        for (size_t i = 0; i < n; ++i) {
            double val = data[i];
            sum_sq += val * val;
        }
    } // end parallel region

    double end = omp_get_wtime();

    double mean     = sum    / (double)n;
    double mean_sq  = sum_sq / (double)n;
    double variance = mean_sq - mean * mean;

    printf("variance       = %.2f\n", variance);
    printf("total time (s) = %.2f\n", end - start);
    printf("num threads    = %d\n", omp_get_max_threads());

    free(data);
    return 0;
}
