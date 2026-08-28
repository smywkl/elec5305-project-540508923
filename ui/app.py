"""Very early UI scaffold for the ELEC5305 project.

The final UI is expected to remain lightweight. It will demonstrate the
signal-processing system rather than become the main technical contribution.
"""

try:
    import streamlit as st
except ImportError:
    st = None


def main():
    if st is None:
        raise RuntimeError("Install streamlit before running the UI.")

    st.title("Dynamic Binaural Music Spatialisation")
    st.caption("ELEC5305 project prototype — early scaffold")

    audio = st.file_uploader("Load stereo music", type=["wav", "mp3", "flac"])

    st.subheader("Planned stem positions")
    vocals = st.slider("Vocals azimuth (degrees)", -90, 90, 0)
    drums_start = st.slider("Drums start azimuth", -90, 90, 60)
    drums_end = st.slider("Drums end azimuth", -90, 90, -60)
    bass = st.slider("Bass azimuth (degrees)", -90, 90, -30)
    other = st.slider("Other azimuth (degrees)", -90, 90, -60)

    st.write({
        "vocals": vocals,
        "drums_start": drums_start,
        "drums_end": drums_end,
        "bass": bass,
        "other": other,
    })

    if st.button("Generate binaural mix"):
        st.info("Processing pipeline not connected yet — this is the Week 4 UI scaffold.")

    if audio is not None:
        st.audio(audio)


if __name__ == "__main__":
    main()
