export function initSidebar() {
  const shell = document.querySelector('.app-shell');
  const sidebar = document.getElementById('left-sidebar');
  const toggleBtn = document.getElementById('sidebar-toggle-btn');

  if (!sidebar || !toggleBtn || !shell) return;

  const applyState = (isCollapsed) => {
    shell.classList.toggle('is-sidebar-collapsed', isCollapsed);
    const icon = toggleBtn.querySelector('i');
    if (icon) {
      icon.className = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-bars';
    }
    toggleBtn.title = isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar';
  };

  let isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
  applyState(isCollapsed);

  toggleBtn.addEventListener('click', () => {
    isCollapsed = !isCollapsed;
    localStorage.setItem('sidebar-collapsed', isCollapsed);
    applyState(isCollapsed);
  });
}