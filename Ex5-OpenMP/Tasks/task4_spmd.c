#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

int main(void) {
    const size_t n = 1000000000;
    double *data = malloc(n * sizeof *data);
    if (!data) { return 1; }

    double start = omp_get_wtime();

    double sum    = 0.0;
    double sum_sq = 0.0;

    #pragma omp parallel
    {
        int tid       = omp_get_thread_num();
        int nthreads  = omp_get_num_threads();

        size_t chunk  = n / nthreads;
        size_t begin  = tid * chunk;
        size_t end    = (tid == nthreads - 1) ? n : begin + chunk;

        double local_sum    = 0.0;
        double local_sum_sq = 0.0;

        for (size_t i = begin; i < end; ++i) {
            data[i] = i % 10;
        }

        #pragma omp barrier

        for (size_t i = begin; i < end; ++i) {
            local_sum += data[n - 1 - i];
        }

        #pragma omp barrier

        for (size_t i = begin; i < end; ++i) {
            local_sum_sq += data[i] * data[i];
        }

        #pragma omp atomic
        sum += local_sum;

        #pragma omp atomic
        sum_sq += local_sum_sq;
    } // end parallel region

    double end = omp_get_wtime();

    double mean     = sum    / (double)n;
    double mean_sq  = sum_sq / (double)n;
    double variance = mean_sq - mean * mean;

    printf("variance = %.2f\n", variance);
    printf("total time (s) = %.2f\n", end - start);
    printf("num threads = %d\n\n", omp_get_max_threads());

    free(data);
    return 0;
}
