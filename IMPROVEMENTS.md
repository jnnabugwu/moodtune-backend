# Audio Analysis Service Improvements

This document tracks potential improvements to the audio analysis service beyond the initial MVP implementation.

## Energy Normalization

### Current Issue
Energy normalization uses hardcoded min/max values (0, 0.5) which assumes RMS values from librosa will never exceed 0.5. This is an arbitrary assumption that may not hold for all audio files, potentially causing:
- Values > 0.5 to be clamped to 1.0
- Loss of dynamic range for quieter tracks
- Inconsistent energy values across different audio sources

### Proposed Solution

**Option 1: Adaptive Normalization (Recommended)**
- Calculate min/max from the actual RMS feature array: `rms.min()` and `rms.max()`
- Normalize using the observed range: `(value - rms.min()) / (rms.max() - rms.min())`
- Pros: Adapts to each track's actual dynamic range
- Cons: May not be directly comparable across tracks (but this might be fine for mood classification)

**Option 2: Statistical Normalization**
- Use percentile-based normalization (e.g., 5th and 95th percentiles)
- More robust to outliers than min/max
- Formula: `(value - p5) / (p95 - p5)`, then clamp to [0, 1]

**Option 3: Reference-Based Normalization**
- Use a fixed reference range based on empirical analysis of Spotify previews
- Analyze a sample of tracks to determine typical RMS ranges
- Set min/max based on observed distribution (e.g., 0.01 to 0.8)
- Pros: Consistent scale across tracks
- Cons: Requires data collection and may need periodic updates

**Option 4: Logarithmic Normalization**
- Use log scale for RMS (since audio perception is logarithmic)
- Formula: `log10(value + epsilon) / log10(max_expected + epsilon)`
- Better matches human perception of loudness

### Recommendation
Start with **Option 1** (adaptive normalization) as it's simple and works well for mood classification. If cross-track comparability becomes important, move to **Option 3** with empirically-derived ranges.

---

## Valence Estimation

### Current Approach
Uses brightness (spectral centroid) and tempo with fixed weights (60% brightness, 40% tempo).

### Potential Improvements
- Add chroma features (already extracted but not fully utilized)
- Consider harmonic vs. percussive separation
- Add key detection (major keys tend to sound happier)
- Use machine learning model trained on Spotify's valence data (if available)

---

## Danceability Estimation

### Current Approach
Based on tempo distance from optimal (110 BPM) and energy.

### Potential Improvements
- Add beat strength/regularity metrics
- Consider time signature detection
- Analyze rhythmic patterns (syncopation, swing)
- Use onset detection to measure beat consistency

---

## Audio Feature Extraction

### Current Features
- Tempo (BPM)
- Energy (RMS)
- Brightness (spectral centroid)
- Chroma (harmony)
- Loudness (dB)

### Additional Features to Consider
- **Zero Crossing Rate**: Roughness/noisiness indicator
- **Spectral Rolloff**: Frequency below which 85% of energy is contained
- **MFCCs**: Mel-frequency cepstral coefficients for timbre
- **Tempo Stability**: Variance in tempo over time
- **Dynamic Range**: Difference between loudest and quietest parts
- **Harmonic/Percussive Separation**: Better mood indicators

---

## Error Handling & Edge Cases

### Current Issues
- Default features returned on any error (may mask real problems)
- No validation of preview URL before download
- No handling for very short previews (< 10 seconds)
- No handling for corrupted/invalid audio files

### Improvements
- More granular error handling (network errors vs. audio processing errors)
- Validate preview URL format before attempting download
- Check audio duration before processing
- Add audio format validation (ensure it's actually audio)
- Log specific error types for debugging
- Return partial results if some features fail but others succeed

---

## Performance Optimizations

### Current Bottlenecks
- Downloads entire 30-second preview even if we only need a portion
- Processes full audio even though we limit to 30 seconds
- No caching of analysis results

### Improvements
- Stream audio instead of downloading full file
- Process audio in chunks for very long previews
- Cache analysis results by track ID (with TTL)
- Parallel processing of multiple features where possible
- Use librosa's faster processing options (e.g., `n_fft` parameter tuning)

---

## Accuracy Improvements

### Validation & Testing
- Create test suite with known mood tracks
- Compare results against Spotify's audio features API (when available)
- A/B test different normalization approaches
- Collect user feedback on mood accuracy

### Model Refinement
- Collect ground truth data (user-labeled moods)
- Train a simple ML model (e.g., logistic regression) on extracted features
- Fine-tune weights based on validation set performance
- Consider ensemble methods combining multiple approaches

---

## Code Quality

### Refactoring Opportunities
- Extract feature extraction into separate methods
- Create a feature extraction pipeline/chain
- Add type hints for all return values
- Add docstrings with examples
- Create unit tests for each feature extraction method
- Add integration tests with sample audio files

---

## API Enhancements

### Current Endpoints
- `/song/analyze/{track_id}` - Analyzes by track ID
- `/song/analyze` - Analyzes from preview URL

### Potential Additions
- Batch analysis endpoint (analyze multiple tracks at once)
- Analysis with custom parameters (e.g., different normalization methods)
- Comparison endpoint (compare two tracks' moods)
- Analysis history endpoint (track what's been analyzed)

---

## Documentation

### Missing Documentation
- API endpoint documentation (beyond docstrings)
- Audio feature explanation guide
- Mood classification methodology
- Troubleshooting guide for common errors
- Performance benchmarks and expected response times
