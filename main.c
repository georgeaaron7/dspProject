#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include "tone_1k.c"     // Generated from your .wav
#include <dsplib.h>
#include "platform.h"    // TI Board support
#include "gpio_api.h"

#define FRAME_SIZE 1024
#define SAMPLE_RATE 44100

/* --- Buffers --- */
float window[FRAME_SIZE];
float fftInput[FRAME_SIZE];
float fftOutput[2*FRAME_SIZE];
float twiddle[FRAME_SIZE];

/* --- Indices --- */
int sampleIndex = 0;

/* --- Function Prototypes --- */
void initWindow();
void initFFT();
void loadNextFrame();
void computeFFT();
int getDominantBand();
void setLEDs(int band);
void delay_ms(uint32_t ms);

/* ------------------------------ */
/* -------- MAIN ---------------- */
/* ------------------------------ */

void main(void)
{
    platform_init();     // Initializes board clocks, PLL, DDR, GPIO, etc.
    GPIO_init();         // Initialize GPIO for LED control

    initWindow();
    initFFT();

    printf("\n=== DSP Frequency Visualizer (TMS320C6748) ===\n");

    while (1)
    {
        loadNextFrame();
        computeFFT();
        int band = getDominantBand();
        setLEDs(band);
        delay_ms(50);    // simulate ~20 fps
    }
}

/* ------------------------------ */
/* ------- FUNCTIONS ------------ */
/* ------------------------------ */

void initWindow()
{
    for (int i = 0; i < FRAME_SIZE; i++)
        window[i] = 0.54 - 0.46 * cosf(2 * M_PI * i / (FRAME_SIZE - 1));
}

void initFFT()
{
    gen_twiddle_fft_sp(twiddle, FRAME_SIZE);
}

void loadNextFrame()
{
    for (int i = 0; i < FRAME_SIZE; i++)
    {
        fftInput[i] = (float)tone_1k[(sampleIndex + i) % 44100] * window[i];
    }
    sampleIndex = (sampleIndex + FRAME_SIZE) % 44100;
}

void computeFFT()
{
    DSPF_sp_fftSPxSP(FRAME_SIZE, fftInput, twiddle, fftOutput, 0, FRAME_SIZE);
}

/* Find dominant frequency band */
int getDominantBand()
{
    float maxMag = 0.0f;
    int maxIndex = 0;

    for (int k = 0; k < FRAME_SIZE/2; k++)
    {
        float re = fftOutput[2*k];
        float im = fftOutput[2*k + 1];
        float mag = sqrtf(re*re + im*im);
        if (mag > maxMag) {
            maxMag = mag;
            maxIndex = k;
        }
    }

    float freq = (float)maxIndex * SAMPLE_RATE / FRAME_SIZE;

    if (freq < 500.0f)
        return 0;   // Low
    else if (freq < 2000.0f)
        return 1;   // Mid
    else
        return 2;   // High
}

/* LED Mapping: LED0=Low, LED1=Mid, LED2=High */
void setLEDs(int band)
{
    GPIO_setOutput(GPIO_BANK_LED0, GPIO_PIN_LED0, GPIO_LOW);
    GPIO_setOutput(GPIO_BANK_LED1, GPIO_PIN_LED1, GPIO_LOW);
    GPIO_setOutput(GPIO_BANK_LED2, GPIO_PIN_LED2, GPIO_LOW);

    switch (band)
    {
        case 0:
            GPIO_setOutput(GPIO_BANK_LED0, GPIO_PIN_LED0, GPIO_HIGH);
            break;
        case 1:
            GPIO_setOutput(GPIO_BANK_LED1, GPIO_PIN_LED1, GPIO_HIGH);
            break;
        case 2:
            GPIO_setOutput(GPIO_BANK_LED2, GPIO_PIN_LED2, GPIO_HIGH);
            break;
    }
}

/* Delay function (simple busy-wait) **/
void delay_ms(uint32_t ms)
{
    volatile uint32_t i, j;
    for (i = 0; i < ms; i++)
        for (j = 0; j < 10000; j++);
}
