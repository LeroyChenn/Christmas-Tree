import streamlit as st
import streamlit.components.v1 as components

# 设置页面配置
st.set_page_config(layout="wide", page_title="Gesture Controlled Christmas Tree")

st.title("🎄 手势控制粒子圣诞树")
st.markdown("""
**操作说明:**
1. **允许摄像头权限**（数据仅在本地处理，不会上传）。
2. **手掌张开** 🖐️：金色光点与装饰物**聚合**成圣诞树。
3. **手掌握拳** ✊：圣诞树**炸开**成满天星辰。
4. **左右挥手** 👋：控制视角的**旋转**。
""")

# 核心 HTML/JS 代码
# 我们将 JavaScript 直接嵌入 Python，利用前端算力实现 60FPS 流畅体验
html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        body { margin: 0; overflow: hidden; background-color: #050505; color: white; font-family: sans-serif; }
        #canvas-container { width: 100vw; height: 80vh; position: relative; }
        video { position: absolute; top: 10px; left: 10px; width: 160px; height: 120px; border-radius: 10px; transform: scaleX(-1); opacity: 0.7; z-index: 10; border: 2px solid gold; }
        #loading { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 24px; color: gold; pointer-events: none; }
    </style>
    <!-- 引入 Three.js 和 MediaPipe -->
    <script type="importmap">
      {
        "imports": {
          "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/",
          "@mediapipe/tasks-vision": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.8/+esm"
        }
      }
    </script>
</head>
<body>
    <div id="canvas-container">
        <video id="webcam" autoplay playsinline></video>
        <div id="loading">正在加载 AI 模型与 3D 引擎...</div>
    </div>

    <script type="module">
        import * as THREE from 'three';
        import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';

        // --- 全局变量 ---
        let scene, camera, renderer;
        let particles, particleGeo, particleMat;
        let decorations = []; // 存储装饰物Mesh
        let clock = new THREE.Clock();
        
        // 状态变量
        let targetAggregation = 0; // 0 = 散开, 1 = 聚合
        let currentAggregation = 0;
        let targetRotation = 0;
        let currentRotation = 0;

        // --- 初始化场景 ---
        function initScene() {
            const container = document.getElementById('canvas-container');
            
            scene = new THREE.Scene();
            scene.fog = new THREE.FogExp2(0x050505, 0.002);

            camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.position.z = 30;
            camera.position.y = 15;
            camera.lookAt(0, 10, 0);

            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            // 灯光
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            const pointLight = new THREE.PointLight(0xffd700, 2, 50);
            pointLight.position.set(0, 20, 10);
            scene.add(pointLight);

            createTreeParticles();
            createDecorations();
            
            // 窗口调整
            window.addEventListener('resize', () => {
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            });
        }

        // --- 创建金色粒子树 ---
        function createTreeParticles() {
            const particleCount = 4000;
            const positions = [];
            const targetPositions = [];
            const colors = [];
            const colorObj = new THREE.Color();

            for (let i = 0; i < particleCount; i++) {
                // 1. 目标位置：圆锥体 (圣诞树形状)
                // 螺旋上升算法
                const angle = i * 0.1;
                const height = Math.random() * 30; // 树高 0-30
                const radius = (30 - height) * 0.4 * Math.random(); // 底部宽，顶部窄
                const helixAngle = height * 2.0 + Math.random() * Math.PI * 2;
                
                const tx = Math.cos(helixAngle) * radius;
                const ty = height;
                const tz = Math.sin(helixAngle) * radius;

                // 2. 初始随机位置 (散开状态)
                const rx = (Math.random() - 0.5) * 100;
                const ry = (Math.random() - 0.5) * 100;
                const rz = (Math.random() - 0.5) * 100;

                positions.push(rx, ry, rz); // 当前位置
                targetPositions.push(tx, ty, tz); // 聚合位置 (自定义属性)

                // 颜色：金色为主，偶尔闪烁白色
                if (Math.random() > 0.9) colorObj.setHex(0xffffff);
                else colorObj.setHex(0xffd700);
                
                colors.push(colorObj.r, colorObj.g, colorObj.b);
            }

            particleGeo = new THREE.BufferGeometry();
            particleGeo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            particleGeo.setAttribute('targetPosition', new THREE.Float32BufferAttribute(targetPositions, 3));
            particleGeo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

            // 保存初始随机位置以便后续计算（虽然可以直接算，但存起来方便）
            particleGeo.userData = { initialPositions: [...positions] };

            particleMat = new THREE.PointsMaterial({ 
                size: 0.4, 
                vertexColors: true, 
                blending: THREE.AdditiveBlending, 
                depthWrite: false,
                transparent: true,
                opacity: 0.8
            });

            particles = new THREE.Points(particleGeo, particleMat);
            scene.add(particles);
        }

        // --- 创建装饰物 (几何体) ---
        function createDecorations() {
            // 辅助函数：创建装饰物逻辑
            function addDecoration(type, color, yRange, count) {
                const geometry = type === 'box' ? new THREE.BoxGeometry(1.5, 1.5, 1.5) : 
                                 type === 'sphere' ? new THREE.SphereGeometry(0.8, 16, 16) :
                                 new THREE.ConeGeometry(0.5, 3, 8); // 姜饼人/糖果简易替代
                
                const material = new THREE.MeshStandardMaterial({ 
                    color: color, 
                    roughness: 0.3, 
                    metalness: 0.7,
                    emissive: color,
                    emissiveIntensity: 0.2
                });

                for (let i = 0; i < count; i++) {
                    const mesh = new THREE.Mesh(geometry, material);
                    
                    // 计算树上的位置
                    const height = Math.random() * (yRange[1] - yRange[0]) + yRange[0];
                    const radius = (30 - height) * 0.4; // 树的半径
                    const angle = Math.random() * Math.PI * 2;
                    
                    const tx = Math.cos(angle) * radius;
                    const ty = height;
                    const tz = Math.sin(angle) * radius;

                    // 散开位置
                    const rx = (Math.random() - 0.5) * 80;
                    const ry = (Math.random() - 0.5) * 80;
                    const rz = (Math.random() - 0.5) * 80;

                    mesh.position.set(rx, ry, rz);
                    mesh.userData = { 
                        targetPos: new THREE.Vector3(tx, ty, tz),
                        randomPos: new THREE.Vector3(rx, ry, rz),
                        rotationSpeed: Math.random() * 0.05
                    };
                    
                    // 随机旋转
                    mesh.rotation.set(Math.random(), Math.random(), Math.random());
                    
                    scene.add(mesh);
                    decorations.push(mesh);
                }
            }

            // 1. 礼物盒 (红、绿、蓝)
            addDecoration('box', 0xff0000, [0, 10], 15);
            addDecoration('box', 0x00ff00, [0, 10], 15);
            
            // 2. 彩球 (金、银、红)
            addDecoration('sphere', 0xff0000, [5, 25], 20);
            addDecoration('sphere', 0xc0c0c0, [5, 25], 20);

            // 3. 树顶铃铛 (组合几何体)
            const bellGroup = new THREE.Group();
            
            const bellBody = new THREE.Mesh(
                new THREE.CylinderGeometry(0.5, 2, 3, 32, 1, true),
                new THREE.MeshStandardMaterial({ color: 0xffd700, side: THREE.DoubleSide, metalness: 1, roughness: 0.2 })
            );
            const bellBall = new THREE.Mesh(
                new THREE.SphereGeometry(0.8),
                new THREE.MeshStandardMaterial({ color: 0xffd700 })
            );
            bellGroup.add(bellBody);
            bellGroup.add(bellBall);
            
            // 铃铛位置
            const bellTx = 0, bellTy = 31, bellTz = 0;
            const bellRx = 0, bellRy = 50, bellRz = 0;

            bellGroup.position.set(bellRx, bellRy, bellRz);
            bellGroup.rotation.z = 0.2;
            bellGroup.userData = {
                 targetPos: new THREE.Vector3(bellTx, bellTy, bellTz),
                 randomPos: new THREE.Vector3(bellRx, bellRy, bellRz),
                 rotationSpeed: 0
            };
            scene.add(bellGroup);
            decorations.push(bellGroup);
        }

        // --- 动画循环 ---
        function animate() {
            requestAnimationFrame(animate);
            const delta = clock.getDelta();
            const time = clock.getElapsedTime();

            // 1. 平滑插值聚合度 (Lerp)
            // 靠近 1 是聚合，靠近 0 是散开
            currentAggregation += (targetAggregation - currentAggregation) * 0.1;
            
            // 2. 平滑插值旋转 (Lerp)
            currentRotation += (targetRotation - currentRotation) * 0.05;

            // --- 更新粒子 ---
            const posAttr = particleGeo.attributes.position;
            const targetAttr = particleGeo.attributes.targetPosition;
            const initPos = particleGeo.userData.initialPositions;

            for (let i = 0; i < posAttr.count; i++) {
                // 原始随机位置
                const rx = initPos[i * 3];
                const ry = initPos[i * 3 + 1];
                const rz = initPos[i * 3 + 2];

                // 目标树位置
                const tx = targetAttr.array[i * 3];
                const ty = targetAttr.array[i * 3 + 1];
                const tz = targetAttr.array[i * 3 + 2];

                // 混合：位置 = 随机 + (目标 - 随机) * 聚合度
                // 增加一点噪声让飞行过程更有趣
                const noise = Math.sin(time * 2 + i) * 0.2 * (1 - currentAggregation);

                posAttr.array[i * 3] = rx + (tx - rx) * currentAggregation + noise;
                posAttr.array[i * 3 + 1] = ry + (ty - ry) * currentAggregation + noise;
                posAttr.array[i * 3 + 2] = rz + (tz - rz) * currentAggregation + noise;
            }
            posAttr.needsUpdate = true;
            
            // 粒子整体旋转
            particles.rotation.y = time * 0.1 + currentRotation * Math.PI; // 自动旋转 + 手势旋转

            // --- 更新装饰物 ---
            decorations.forEach(mesh => {
                const tPos = mesh.userData.targetPos;
                const rPos = mesh.userData.randomPos;

                mesh.position.x = rPos.x + (tPos.x - rPos.x) * currentAggregation;
                mesh.position.y = rPos.y + (tPos.y - rPos.y) * currentAggregation;
                mesh.position.z = rPos.z + (tPos.z - rPos.z) * currentAggregation;

                mesh.rotation.x += mesh.userData.rotationSpeed;
                mesh.rotation.y += mesh.userData.rotationSpeed;
                
                // 装饰物围绕中心公转
                // 为了简单，我们只让整个场景组旋转，或者计算每个物体的旋转
                // 这里我们做简单的绕Y轴旋转计算
                const axis = new THREE.Vector3(0, 1, 0);
                const angle = (time * 0.1 + currentRotation * Math.PI) - particles.rotation.y; 
                // 上面这行有点多余，因为Mesh是独立添加的，需要手动应用公转
                
                // 简便方法：将装饰物加到一个 Group 里一起旋转，这里为了演示位置插值，手动计算旋转后的位置
                // 重新映射位置到旋转后的坐标
                const x = mesh.position.x;
                const z = mesh.position.z;
                // 注意：这里不做复杂的公转逻辑了，直接让它们跟着摄像机视角的相对关系（简化处理）
                // 更好的方式：把 decorations 放到一个 Group 里，旋转 Group
            });
            
            // 为了让装饰物和粒子一起旋转，最好的办法是旋转 camera 或者 旋转整个容器
            // 这里我们采用：旋转 Camera Parent 或者 旋转场景根节点
            // 简单起见，我们旋转 camera 的轨道
            const radius = 40;
            const camAngle = time * 0.2 + currentRotation * 2; // 自动慢速 + 手势
            camera.position.x = Math.sin(camAngle) * radius;
            camera.position.z = Math.cos(camAngle) * radius;
            camera.lookAt(0, 15, 0);

            renderer.render(scene, camera);
        }

        // --- MediaPipe 手势识别逻辑 ---
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
            
            // 获取摄像头
            navigator.mediaDevices.getUserMedia({ video: true }).then((stream) => {
                video.srcObject = stream;
                video.addEventListener("loadeddata", predictWebcam);
            });

            let lastVideoTime = -1;
            
            async function predictWebcam() {
                if (video.currentTime !== lastVideoTime) {
                    lastVideoTime = video.currentTime;
                    const results = handLandmarker.detectForVideo(video, performance.now());
                    
                    if (results.landmarks && results.landmarks.length > 0) {
                        const landmarks = results.landmarks[0]; // 只取第一只手
                        
                        // 1. 计算手掌开合度 (聚合控制)
                        // 取食指指尖(8) 与 手腕(0) 的距离，以及拇指(4) 与 小指(20) 的距离作为参考
                        // 更简单：计算所有指尖到手腕的平均距离
                        const wrist = landmarks[0];
                        const tips = [4, 8, 12, 16, 20];
                        let totalDist = 0;
                        tips.forEach(idx => {
                            const dx = landmarks[idx].x - wrist.x;
                            const dy = landmarks[idx].y - wrist.y;
                            totalDist += Math.sqrt(dx*dx + dy*dy);
                        });
                        const avgDist = totalDist / 5;
                        
                        // 阈值调整 (经验值)
                        // 握拳时 avgDist 约 0.1-0.2，张开时 约 0.4-0.6
                        // 映射到 0 (散开) 到 1 (聚合)
                        let openFactor = (avgDist - 0.2) * 2.5; 
                        openFactor = Math.max(0, Math.min(1, openFactor));
                        
                        targetAggregation = openFactor; // 更新全局目标

                        // 2. 计算手的 X 坐标 (旋转控制)
                        // MediaPipe x 坐标 0-1 (左-右)
                        // 0 -> 旋转 -1, 1 -> 旋转 1
                        const handX = landmarks[9].x; // 使用中指根部作为手的中心
                        targetRotation = (0.5 - handX) * 4; // 乘系数放大灵敏度

                    } else {
                        // 没检测到手，默认聚合
                        targetAggregation = 1; 
                    }
                }
                
                requestAnimationFrame(predictWebcam);
            }
            
            document.getElementById('loading').style.display = 'none';
        }

        // --- 启动 ---
        initScene();
        initHandTracking();
        animate();

    </script>
</body>
</html>
"""

# 在 Streamlit 中渲染 HTML 组件
# height=800 确保有足够的显示空间
components.html(html_code, height=800)