# Face detector weights

`yunet.onnx` is YuNet, a face detector. The file is taken as is from
the OpenCV model zoo:

    https://github.com/opencv/opencv_zoo
    models/face_detection_yunet/face_detection_yunet_2026may.onnx

**License: MIT**, the text is next to it in `yunet-LICENSE.txt`.
Author: Shiqi Yu. MIT allows shipping it as part of anything and asks
for one thing: include that text. It's included.

**Why this version and not the earlier `2023mar`.** The earlier one has
its input size built into the model — 640×640 — so every frame would
have to be squeezed into a square, losing small faces and proportions.
This one accepts any input size, and the frame goes in as it is.

**Why the weights ship with Vertcut instead of being downloaded on first
launch.** The speech recognition model is downloaded on first launch,
and that makes sense — it's 460 MB. This file is 230 KB: downloading it
would add a possible failure ("no internet") where there didn't need to
be one.
