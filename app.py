import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="Christmas Tree 3D")

st.title("🎄 手势控制圣诞树 (调试版)")

# 侧边栏显示状态
with st.sidebar:
    st.markdown("### 🛠 调试指南")
    st.markdown("如果右侧屏幕全白或卡在加载中：")
    st.markdown("1. 确保已连接互联网（需要加载 Three.js 和 AI 模型）。")
    st.markdown("2. **国内用户**可能需要开启 VPN，因为 `unpkg` 和 `jsdelivr` CDN 可能会被拦截。")
    st.markdown("3. 允许浏览器使用**摄像头**权限。")

html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        body { margin: 0; overflow: hidden; background-color: #000; color: white; font-family: monospace; }
        #canvas-container { width: 100%; height: 80vh; position: relative; }
        video { position: absolute; top: 10px; left: 10px; width: 160px; height: 120px; border-radius: 10px; transform: scaleX(-1); opacity: 0.6; z-index: 10; border: 1px solid gold; display: none; }
        
        /* 状态显示区 */
        #status-panel { 
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); 
            text-align: center; pointer-events: none; z-index: 20;
        }
        #loading-text { font-size: 24px; color: gold; margin-bottom: 10px; }
        #error-log { color: #ff4444; background: rgba(0,0,0,0.8); padding: 10px; border-radius: 5px; text-align: left; display: none; max-width: 80%; }
    </style>
    
    <!-- 引入 importmap -->
    <script type="importmap">
      {
        "imports": {
          "three": "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/",
          "@mediapipe/tasks-vision": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/+esm"
        }
      }
    </script>
</head>
<body>
    <div id="canvas-container">
        <video id="webcam" autoplay playsinline></video>
        <div id="status-panel">
            <div id="loading-text">正在初始化引擎...<br><span style="font-size:14px; color:white">请稍候 (首次加载AI模型约需10-30秒)</span></div>
            <div id="error-log"></div>
        </div>
    </div>

    <script type="module">
        // --- 错误捕获系统 ---
        const errLog = document.getElementById('error-log');
        const loadText = document.getElementById('loading-text');
        
        function showError(msg) {
            loadText.style.display = 'none';
            errLog.style.display = 'block';
            errLog.innerHTML += `❌ ${msg}<br>`;
            console.error(msg);
        }

        window.onerror = function(message, source, lineno, colno, error) {
            showError(`JS Error: ${message}`);
        };

        // --- 尝试导入库 ---
        let THREE, FilesetResolver, HandLandmarker;
        
        try {
            THREE = await import('three');
            const Vision = await import('@mediapipe/tasks-vision');
            FilesetResolver = Vision.FilesetResolver;
            HandLandmarker = Vision.HandLandmarker;
        } catch (e) {
            showError("无法加载依赖库。请检查网络连接 (可能需要VPN访问 CDN)。<br>详细: " + e.message);
            throw e;
        }

        // --- 核心逻辑开始 ---
        let scene, camera, renderer, particles, decorations = [];
        let targetAggregation = 1, currentAggregation = 1; // 默认先聚合
        let targetRotation = 0, currentRotation = 0;
        const clock = new THREE.Clock();

        async function main() {
            try {
                initScene();
                loadText.innerText = "正在加载 AI 手势模型 (下载中)...";
                await initHandTracking();
                
                // 成功启动
                loadText.style.display = 'none';
                document.getElementById('webcam').style.display = 'block';
                animate();
            } catch (e) {
                showError("初始化失败: " + e.message);
            }
        }

        function initScene() {
            const container = document.getElementById('canvas-container');
            scene = new THREE.Scene();
            scene.fog = new THREE.FogExp2(0x050505, 0.002);

            camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.position.set(0, 15, 35);
            camera.lookAt(0, 10, 0);

            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            const pointLight = new THREE.PointLight(0xffd700, 2, 50);
            pointLight.position.set(0, 20, 10);
            scene.add(pointLight);
            scene.add(new THREE.AmbientLight(0xffffff, 0.3));

            createParticles();
            
            window.addEventListener('resize', () => {
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            });
        }

        function createParticles() {
            const count = 3000;
            const pos = [], targetPos = [], colors = [];
            const color = new THREE.Color();
            
            for(let i=0; i<count; i++){
                // 树形 (目标)
                const h = Math.random() * 30;
                const r = (30 - h) * 0.4 * Math.random();
                const angle = h * 2 + Math.random() * Math.PI * 2;
                const tx = Math.cos(angle) * r;
                const ty = h;
                const tz = Math.sin(angle) * r;

                // 随机 (当前)
                const rx = (Math.random() - 0.5) * 60;
                const ry = (Math.random() - 0.5) * 60;
                const rz = (Math.random() - 0.5) * 60;

                pos.push(rx, ry, rz);
                targetPos.push(tx, ty, tz);

                color.setHex(Math.random() > 0.8 ? 0xffffff : 0xffd700);
                colors.push(color.r, color.g, color.b);
            }

            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
            geo.setAttribute('target', new THREE.Float32BufferAttribute(targetPos, 3));
            geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
            geo.userData = { initial: [...pos] };

            const mat = new THREE.PointsMaterial({ size: 0.5, vertexColors: true, blending: THREE.AdditiveBlending, transparent: true });
            particles = new THREE.Points(geo, mat);
            scene.add(particles);
        }

        async function initHandTracking() {
            const vision = await FilesetResolver.forVisionTasks(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/wasm"
            );
            
            const handLandmarker = await HandLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`,
                    delegate: "GPU"
                },
                runningMode: "VIDEO",
                numHands: 1
            });

            const video = document.getElementById("webcam");
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            video.srcObject = stream;
            
            video.addEventListener("loadeddata", () => {
                predict(handLandmarker, video);
            });
        }

        function predict(model, video) {
            const now = performance.now();
            const results = model.detectForVideo(video, now);
            
            if (results.landmarks && results.landmarks.length > 0) {
                const marks = results.landmarks[0];
                
                // 1. 开合检测 (指尖到手腕平均距离)
                const wrist = marks[0];
                const tips = [4, 8, 12, 16, 20];
                let dist = 0;
                tips.forEach(i => {
                    dist += Math.sqrt(Math.pow(marks[i].x - wrist.x, 2) + Math.pow(marks[i].y - wrist.y, 2));
                });
                const avgDist = dist / 5;
                // 距离大(张开) -> 聚合(1)，距离小(拳头) -> 散开(0)
                // 修正逻辑：握拳散开，张开聚合
                // 张开时 avgDist ~0.3-0.5, 握拳 ~0.1-0.15
                targetAggregation = Math.min(1, Math.max(0, (avgDist - 0.15) * 4)); 

                // 2. 旋转检测 (手的位置)
                targetRotation = (0.5 - marks[9].x) * 3;
            } else {
                targetAggregation = 1; // 没手时自动聚合
            }

            requestAnimationFrame(() => predict(model, video));
        }

        function animate() {
            requestAnimationFrame(animate);
            const dt = clock.getDelta();
            const time = clock.getElapsedTime();

            currentAggregation += (targetAggregation - currentAggregation) * 0.1;
            currentRotation += (targetRotation - currentRotation) * 0.05;

            // 粒子更新
            const pos = particles.geometry.attributes.position;
            const target = particles.geometry.attributes.target;
            const init = particles.geometry.userData.initial;

            for(let i=0; i<pos.count; i++){
                const idx = i*3;
                // 插值: 初始 -> 目标
                const tx = target.array[idx];
                const ty = target.array[idx+1];
                const tz = target.array[idx+2];
                
                const ix = init[idx];
                const iy = init[idx+1];
                const iz = init[idx+2];

                pos.array[idx]   = ix + (tx - ix) * currentAggregation;
                pos.array[idx+1] = iy + (ty - iy) * currentAggregation;
                pos.array[idx+2] = iz + (tz - iz) * currentAggregation;
            }
            pos.needsUpdate = true;

            // 旋转
            particles.rotation.y = time * 0.1 + currentRotation;
            
            renderer.render(scene, camera);
        }

        main();
    </script>
</body>
</html>
"""

components.html(html_code, height=700)