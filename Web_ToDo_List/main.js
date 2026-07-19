const form = document.getElementById('task-form');
const input = document.getElementById('task-input');
const list = document.getElementById('task-list');

form.addEventListener('submit', function (event) {
  event.preventDefault();

  const taskText = input.value.trim();
  if (taskText === '') return;

  const li = document.createElement('li');

  // Task text
  const textSpan = document.createElement('span');
  textSpan.textContent = taskText;

  // Status button
  const statusBtn = document.createElement('button');
  statusBtn.textContent = 'Not Done';
  statusBtn.className = 'status-btn';
  statusBtn.type = 'button';

  statusBtn.addEventListener('click', function () {
  if (statusBtn.textContent === 'Not Done') {
    statusBtn.textContent = 'Done';
    statusBtn.classList.add('done');   // <-- add this
    li.classList.add('done');
  } else {
    statusBtn.textContent = 'Not Done';
    statusBtn.classList.remove('done'); // <-- remove this
    li.classList.remove('done');
  }

  updateStats();
});

  // Delete button
  const deleteBtn = document.createElement('button');
  deleteBtn.textContent = 'Delete';
  deleteBtn.className = 'delete-btn';
  deleteBtn.type = 'button';

  deleteBtn.addEventListener('click', function (event) {
    event.stopPropagation();
    li.remove();
    updateStats();
  });

  // Build the li
  li.appendChild(textSpan);
  li.appendChild(statusBtn);
  li.appendChild(deleteBtn);

  list.appendChild(li);

  input.value = '';

  updateStats();
});

function updateStats() {
  const items = document.querySelectorAll('#task-list li');
  const total = items.length;

  let done = 0;
  items.forEach(li => {
    if (li.classList.contains('done')) {
      done++;
    }
  });

  const notDone = total - done;

  document.getElementById('total-count').textContent = total;
  document.getElementById('done-count').textContent = done;
  document.getElementById('not-done-count').textContent = notDone;
}
