"""
🎵 Streamlit Audio Silence Remover (Natural Version)
Run with: streamlit run app.py

Install dependencies:
pip install streamlit pydub
"""
import imageio_ffmpeg
from pydub import AudioSegment

# Use the bundled ffmpeg binary
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

import streamlit as st
import imageio_ffmpeg
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import tempfile
import os

st.set_page_config(
    page_title="Audio Silence Remover",
    page_icon="🎧",
    layout="wide"
)

# -------------------------------------------------------------------
# 🧩 Audio Processing Function
# -------------------------------------------------------------------
def process_audio(audio, nonsilent_ranges, original_duration,
                  keep_start, keep_end, min_silence_len):
    """Process and export smoother audio"""
    progress_bar = st.progress(0, text="Smoothing and stitching audio...")

    # Adjust ranges: extend start/end a bit for natural tone
    adjusted_ranges = []
    for (start, end) in nonsilent_ranges:
        start = max(0, start - keep_start)
        end = min(len(audio), end + keep_end)
        adjusted_ranges.append((start, end))

    output_audio = AudioSegment.empty()
    crossfade_dur = 60  # smooth transition between segments (ms)

    for i, (start, end) in enumerate(adjusted_ranges):
        segment = audio[start:end]
        if i == 0:
            output_audio = segment
        else:
            output_audio = output_audio.append(segment, crossfade=crossfade_dur)

        if i % 10 == 0:
            progress = int((i / len(adjusted_ranges)) * 90)
            progress_bar.progress(progress, text=f"Processing segment {i+1}/{len(adjusted_ranges)}...")

    # Light normalization for even loudness
    output_audio = output_audio.normalize(headroom=1.0)

    progress_bar.progress(95, text="Exporting processed audio...")

    output_path = tempfile.mktemp(suffix=".wav")
    output_audio.export(output_path, format="wav")

    progress_bar.progress(100, text="Complete ✅")

    new_duration = len(output_audio) / 1000
    time_saved = original_duration - new_duration

    st.success("✅ Processing Complete — smoother, natural result!")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("New Duration", f"{new_duration:.1f}s", f"-{time_saved:.1f}s")
    with col2:
        st.metric("Time Saved", f"{time_saved/60:.1f} min", f"{(time_saved/original_duration)*100:.1f}%")

    with open(output_path, "rb") as file:
        st.download_button(
            label="⬇️ Download Processed Audio",
            data=file,
            file_name="audio_no_pauses.wav",
            mime="audio/wav",
            use_container_width=True
        )

    os.unlink(output_path)
    progress_bar.empty()

# -------------------------------------------------------------------
# 🖼️ UI
# -------------------------------------------------------------------
st.title("🎧 Natural Audio Silence Remover")
st.markdown("Preview and remove long pauses while keeping a natural flow")

# Sidebar
st.sidebar.header("⚙️ Settings")

silence_thresh = st.sidebar.slider(
    "Silence Threshold (dB)",
    min_value=-60,
    max_value=-20,
    value=-40,
    step=5,
    help="Lower = more sensitive (detects quieter speech)"
)

min_silence_len = st.sidebar.slider(
    "Minimum Silence Length (seconds)",
    min_value=0.5,
    max_value=5.0,
    value=2.0,
    step=0.25,
    help="Only remove pauses longer than this"
)

keep_start = st.sidebar.slider(
    "Keep before speech (ms)",
    0, 1000, 100, 50,
    help="Keep this much room tone before speech"
)
keep_end = st.sidebar.slider(
    "Keep after speech (ms)",
    0, 1000, 150, 50,
    help="Keep this much room tone after speech"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 💡 Tips")
st.sidebar.markdown("- Lower threshold catches more subtle speech")
st.sidebar.markdown("- Keep small start/end ms for smoother tone")
st.sidebar.markdown("- Re-analyze if results sound too abrupt")

# -------------------------------------------------------------------
# 🔊 File Upload + Analysis
# -------------------------------------------------------------------
if "audio" not in st.session_state:
    st.session_state.audio = None
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

uploaded_file = st.file_uploader(
    "Upload your audio file",
    type=["mp3", "wav", "m4a", "ogg", "flac"],
    help="Upload an audio file up to your configured size limit"
)

if uploaded_file is not None:
    if st.session_state.audio is None or st.session_state.get("last_file") != uploaded_file.name:
        with st.spinner("Loading audio file..."):
            if st.session_state.audio_path and os.path.exists(st.session_state.audio_path):
                os.unlink(st.session_state.audio_path)

            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                tmp_file.write(uploaded_file.read())
                st.session_state.audio_path = tmp_file.name

            st.session_state.audio = AudioSegment.from_file(st.session_state.audio_path)
            st.session_state.last_file = uploaded_file.name
            st.session_state.analyzed = False

    audio = st.session_state.audio
    original_duration = len(audio) / 1000

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📁 **File:** {uploaded_file.name}")
    with col2:
        st.info(f"📊 **Size:** {uploaded_file.size / 1024 / 1024:.2f} MB")
    with col3:
        st.info(f"⏱️ **Duration:** {original_duration:.1f}s ({original_duration/60:.1f} min)")

    st.markdown("---")

    col1, col2 = st.columns([1, 3])
    with col1:
        analyze_button = st.button("🔍 Analyze Pauses", use_container_width=True)

    if analyze_button:
        with st.spinner("Detecting silence..."):
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=int(min_silence_len * 1000),
                silence_thresh=silence_thresh,
                seek_step=100
            )
            st.session_state.nonsilent_ranges = nonsilent_ranges
            st.session_state.analyzed = True

    # ---------------------------------------------------------------
    # 🧮 Show Analysis
    # ---------------------------------------------------------------
    if st.session_state.analyzed and "nonsilent_ranges" in st.session_state:
        nonsilent_ranges = st.session_state.nonsilent_ranges

        pauses = []
        total_silence = 0
        for i in range(len(nonsilent_ranges) - 1):
            end_current = nonsilent_ranges[i][1] / 1000
            start_next = nonsilent_ranges[i + 1][0] / 1000
            silence_duration = start_next - end_current
            if silence_duration >= min_silence_len:
                pauses.append({
                    "pause_num": len(pauses) + 1,
                    "start": end_current,
                    "end": start_next,
                    "duration": silence_duration
                })
                total_silence += silence_duration

        st.success("✅ Analysis Complete!")

        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Speech Segments", len(nonsilent_ranges))
        with col2: st.metric("Long Pauses Found", len(pauses))
        with col3: st.metric("Total Silence", f"{total_silence:.1f}s")
        with col4: st.metric("Silence %", f"{(total_silence / original_duration) * 100:.1f}%")

        if pauses:
            st.markdown("### 📊 Long Pauses Preview")
            table_data = [{
                "#": p["pause_num"],
                "Start": f"{p['start']:.2f}s",
                "End": f"{p['end']:.2f}s",
                "Duration": f"{p['duration']:.2f}s"
            } for p in pauses]
            st.dataframe(table_data, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### 🚀 Ready to Process?")
            st.info(f"💡 Will remove {len(pauses)} long pauses totaling {total_silence:.1f}s")

            if st.button("✂️ Remove Pauses & Download", type="primary", use_container_width=True):
                process_audio(audio, nonsilent_ranges, original_duration,
                              keep_start, keep_end, min_silence_len)
        else:
            st.warning("⚠️ No long pauses found. Try lowering the minimum silence length.")
    else:
        st.info("👆 Click **Analyze Pauses** to preview what will be removed")

else:
    st.info("👆 Upload an audio file to get started")
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        ### Steps
        1. Upload an audio file (MP3, WAV, etc.)
        2. Adjust silence threshold and lengths
        3. Click **Analyze Pauses**
        4. Review detected pauses and preview
        5. Click **Remove Pauses & Download** for smoother result
        """)

# Footer
st.markdown("---")
st.markdown("Made with ❤️ using Streamlit | Natural Audio Silence Remover")


