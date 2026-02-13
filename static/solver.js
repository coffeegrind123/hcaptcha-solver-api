class CaptchaSolver {
    constructor(taskId, requestType, createdAt) {
        this.taskId = taskId;
        this.requestType = requestType;
        this.createdAt = createdAt;
        this.answers = [];
        this.submitted = false;
        this.dragLines = [];

        this.img = document.getElementById('challenge-img');
        this.container = document.getElementById('challenge-container');
        this.submitBtn = document.getElementById('btn-submit');
        this.preview = document.getElementById('answer-preview');

        this.dragState = null;

        this.img.addEventListener('load', () => this.init());
        if (this.img.complete) this.init();

        this.startTimer();

        new ResizeObserver(() => this.reflowDragLines()).observe(this.container);
    }

    init() {
        if (this.requestType === 'Grid') this.initGrid();
        else if (this.requestType === 'Canvas') this.initCanvas();
        else if (this.requestType === 'Drag') this.initDrag();
    }

    getImageCoords(event) {
        const scaleX = this.img.naturalWidth / this.img.width;
        const scaleY = this.img.naturalHeight / this.img.height;
        let x = event.offsetX * scaleX;
        let y = event.offsetY * scaleY;
        x = Math.max(0, Math.min(this.img.naturalWidth - 1, x));
        y = Math.max(0, Math.min(this.img.naturalHeight - 1, y));
        return { x: Math.round(x), y: Math.round(y) };
    }

    natToPct(natX, natY) {
        return {
            x: natX / this.img.naturalWidth * 100,
            y: natY / this.img.naturalHeight * 100,
        };
    }

    initGrid() {
        const overlay = document.createElement('div');
        overlay.className = 'grid-overlay';
        for (let i = 0; i < 9; i++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            cell.dataset.index = i;
            cell.addEventListener('click', () => this.toggleGridCell(cell, i));
            overlay.appendChild(cell);
        }
        this.container.appendChild(overlay);
    }

    toggleGridCell(cell, index) {
        if (this.submitted) return;
        const pos = this.answers.indexOf(index);
        if (pos >= 0) {
            this.answers.splice(pos, 1);
            cell.classList.remove('selected');
        } else {
            this.answers.push(index);
            cell.classList.add('selected');
        }
        this.updatePreview();
    }

    initCanvas() {
        this.img.style.cursor = 'crosshair';
        this.img.addEventListener('click', (e) => {
            if (this.submitted) return;
            const coords = this.getImageCoords(e);
            this.answers.push([coords.x, coords.y]);
            this.addCanvasMarker(coords.x, coords.y, this.answers.length);
            this.updatePreview();
        });
    }

    addCanvasMarker(natX, natY, num) {
        const pct = this.natToPct(natX, natY);
        const marker = document.createElement('div');
        marker.className = 'canvas-marker';
        marker.textContent = num;
        marker.style.left = pct.x + '%';
        marker.style.top = pct.y + '%';
        this.container.appendChild(marker);
    }

    initDrag() {
        this.img.style.cursor = 'crosshair';
        this.dragState = 'start';
        this.preview.textContent = 'Click START point (green) for drag #1';
        this.img.addEventListener('click', (e) => {
            if (this.submitted) return;
            const coords = this.getImageCoords(e);
            const pct = this.natToPct(coords.x, coords.y);

            if (this.dragState === 'start') {
                this.answers.push([coords.x, coords.y]);
                this.addDragPoint(pct.x, pct.y, 'start');
                this.dragStartPct = { x: pct.x, y: pct.y };
                this.dragState = 'end';
                this.preview.textContent = 'Now click the END point (red)';
            } else if (this.dragState === 'end') {
                this.answers.push([coords.x, coords.y]);
                this.addDragPoint(pct.x, pct.y, 'end');
                this.addDragLine(this.dragStartPct.x, this.dragStartPct.y, pct.x, pct.y);
                this.dragState = 'start';
                this.updatePreview();
            }
        });
    }

    addDragPoint(pctX, pctY, type) {
        const point = document.createElement('div');
        point.className = `drag-point ${type}`;
        point.style.left = pctX + '%';
        point.style.top = pctY + '%';
        this.container.appendChild(point);
    }

    addDragLine(pctX1, pctY1, pctX2, pctY2) {
        const line = document.createElement('div');
        line.className = 'drag-line';
        line.style.left = pctX1 + '%';
        line.style.top = pctY1 + '%';
        line.dataset.pctX1 = pctX1;
        line.dataset.pctY1 = pctY1;
        line.dataset.pctX2 = pctX2;
        line.dataset.pctY2 = pctY2;
        this.container.appendChild(line);
        this.dragLines.push(line);
        this.layoutDragLine(line);
    }

    layoutDragLine(line) {
        const rect = this.container.getBoundingClientRect();
        const x1 = parseFloat(line.dataset.pctX1) / 100 * rect.width;
        const y1 = parseFloat(line.dataset.pctY1) / 100 * rect.height;
        const x2 = parseFloat(line.dataset.pctX2) / 100 * rect.width;
        const y2 = parseFloat(line.dataset.pctY2) / 100 * rect.height;
        const dx = x2 - x1, dy = y2 - y1;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;
        line.style.width = length + 'px';
        line.style.transform = `rotate(${angle}deg)`;
    }

    reflowDragLines() {
        for (const line of this.dragLines) {
            this.layoutDragLine(line);
        }
    }

    clearDragVisuals() {
        this.container.querySelectorAll('.drag-point, .drag-line').forEach(el => el.remove());
        this.dragLines = [];
    }

    updatePreview() {
        if (this.requestType === 'Grid') {
            this.preview.textContent = this.answers.length ? `Selected tiles: ${this.answers.sort((a,b)=>a-b).join(', ')}` : '';
        } else if (this.requestType === 'Canvas') {
            this.preview.textContent = this.answers.length ? `${this.answers.length} point(s) marked` : '';
        } else if (this.requestType === 'Drag') {
            const pairs = Math.floor(this.answers.length / 2);
            if (pairs > 0) {
                const parts = [];
                for (let i = 0; i < pairs; i++) {
                    const s = this.answers[i * 2], e = this.answers[i * 2 + 1];
                    parts.push(`(${s[0]},${s[1]})->(${e[0]},${e[1]})`);
                }
                this.preview.textContent = `${pairs} drag(s): ${parts.join(' | ')}`;
                if (this.answers.length % 2 === 1) {
                    this.preview.textContent += ' | waiting for end point...';
                }
            }
        }
        if (this.requestType === 'Drag') {
            this.submitBtn.disabled = this.answers.length < 2 || this.answers.length % 2 !== 0;
        } else {
            this.submitBtn.disabled = this.answers.length === 0;
        }
    }

    clear() {
        if (this.submitted) return;
        this.answers = [];
        this.container.querySelectorAll('.grid-cell.selected').forEach(c => c.classList.remove('selected'));
        this.container.querySelectorAll('.canvas-marker, .drag-point, .drag-line').forEach(el => el.remove());
        this.dragLines = [];
        if (this.requestType === 'Drag') {
            this.dragState = 'start';
            this.preview.textContent = 'Click START point (green) for drag #1';
        } else {
            this.preview.textContent = '';
        }
        this.submitBtn.disabled = true;
    }

    async submit() {
        if (this.submitted || this.answers.length === 0) return;
        this.submitted = true;
        this.submitBtn.disabled = true;
        this.submitBtn.textContent = 'Submitting...';

        try {
            const resp = await fetch(`/solve/${this.taskId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answers: this.answers }),
            });
            if (resp.ok) {
                document.getElementById('result-overlay').style.display = 'flex';
            } else {
                const data = await resp.json();
                alert('Error: ' + (data.error || 'Unknown error'));
                this.submitted = false;
                this.submitBtn.disabled = false;
                this.submitBtn.textContent = 'Submit';
            }
        } catch (e) {
            alert('Network error: ' + e.message);
            this.submitted = false;
            this.submitBtn.disabled = false;
            this.submitBtn.textContent = 'Submit';
        }
    }

    startTimer() {
        const update = () => {
            const elapsed = Date.now() / 1000 - this.createdAt;
            const remaining = Math.max(0, 120 - Math.floor(elapsed));
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            const display = `${minutes}:${seconds.toString().padStart(2, '0')}`;

            const timerDisplay = document.getElementById('timer-display');
            const timerMessage = document.getElementById('timer-message');
            const timerContainer = document.getElementById('timer');

            timerDisplay.textContent = display;

            if (remaining <= 0) {
                timerContainer.className = 'expired';
                timerMessage.textContent = 'CHALLENGE EXPIRED!';
                timerMessage.className = 'timer-message expired';
                this.submitBtn.disabled = true;
                return;
            } else if (remaining <= 30) {
                timerContainer.className = 'warning';
                timerMessage.textContent = 'Hurry! Time is running out!';
                timerMessage.className = 'timer-message warning';
            } else {
                timerContainer.className = '';
                timerMessage.textContent = '';
                timerMessage.className = 'timer-message';
            }
            requestAnimationFrame(update);
        };
        update();
    }
}

const solver = new CaptchaSolver(TASK_ID, REQUEST_TYPE, CREATED_AT);
