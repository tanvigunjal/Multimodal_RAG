// js/chat.js
import { ChatService } from './ChatService.js';
import { renderBotMessage } from './renderers.js';
import { getChatTitle } from './api.js';

let chatHistory = JSON.parse(localStorage.getItem('chatHistory')) || {};
let activeChatId = localStorage.getItem('activeChatId') || null;
let activeStream = null;

export function initChat() {
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const newChatBtn = document.getElementById('new-chat-btn');
  const clearHistoryBtn = document.getElementById('clear-history-btn');
  const richResponseToggle = document.getElementById('rich-response-toggle');

  // Load chat history from localStorage and ensure proper structure
  const savedHistory = localStorage.getItem('chatHistory');
  try {
    chatHistory = savedHistory ? JSON.parse(savedHistory) : {};
    // Validate chat history structure
    Object.keys(chatHistory).forEach(id => {
      if (!chatHistory[id].messages || !Array.isArray(chatHistory[id].messages)) {
        chatHistory[id].messages = [];
      }
    });
  } catch (e) {
    console.error('Error loading chat history:', e);
    chatHistory = {};
  }
  
  const urlParams = new URLSearchParams(window.location.search);
  const sharedChatId = urlParams.get('chat');

  // Always create a new chat session on page load, unless it's a shared chat
  if (sharedChatId && chatHistory[sharedChatId]) {
    activeChatId = sharedChatId;
  } else {
    // Create new chat session on page load
    activeChatId = createNewChat();
  }

  renderHistoryList();
  loadChat(activeChatId);

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query || sendBtn.disabled) return;

    if (activeStream) {
      activeStream.close();
      activeStream = null;
    }

    const userMessage = { sender: 'user', text: query };
    
    // First add the message to history to ensure it's saved
    addMessageToHistory(userMessage);
    // Then append it to the UI
    appendMessage(userMessage);
    
    chatInput.value = '';
    sendBtn.disabled = true;

    // Now handle the bot's response
    handleStreamQuery(query, richResponseToggle.checked);
  });

  newChatBtn.addEventListener('click', () => {
    if (activeStream) activeStream.close();
    activeChatId = createNewChat();
  });

  clearHistoryBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to clear all chat history?')) {
      if (activeStream) activeStream.close();
      chatHistory = {};
      localStorage.removeItem('chatHistory');
      activeChatId = createNewChat(); // Start a fresh chat
    }
  });

  // Global listener to close the menu when clicking outside
  document.addEventListener('click', (e) => {
    const menu = document.querySelector('.menu-panel');
    const menuButton = e.target.closest('.chat-item-menu-btn');
    if (menu && !menu.contains(e.target) && !menuButton) {
      menu.remove();
    }
  });
}

function handleStreamQuery(query, isRich) {
  // Create and save bot message placeholder immediately
  const botMessage = { sender: 'bot', text: '', sources: [] };
  const botMsgContainer = appendMessage(botMessage);
  const sendBtn = document.getElementById('send-btn');
  
  let fullResponseText = '';
  let sourcesReceived = [];

  // Add empty bot message to history
  addMessageToHistory(botMessage);

  renderBotMessage(botMsgContainer, { streaming: true }); // Initial render

  activeStream = ChatService.streamQuery({
    query,
    rich: isRich,
    onSources: (sources) => {
      sourcesReceived = sources;
      renderBotMessage(botMsgContainer, { text: fullResponseText, sources, streaming: true });
    },
    onToken: (token) => {
      fullResponseText += token;
      renderBotMessage(botMsgContainer, { text: fullResponseText, sources: sourcesReceived, streaming: true });
      scrollToBottom();
    },
    onEnd: (finalText) => {
      renderBotMessage(botMsgContainer, { text: finalText, sources: sourcesReceived, streaming: false });
      const finalMessage = { sender: 'bot', text: finalText, sources: sourcesReceived };
      addMessageToHistory(finalMessage, true);
      sendBtn.disabled = false;
      activeStream = null;
    },
    onError: (error) => {
      const errorText = `Error: ${error.message}`;
      renderBotMessage(botMsgContainer, { text: errorText, sources: [], streaming: false });
      botMsgContainer.style.color = '#dc3545';
      addMessageToHistory({ sender: 'bot', text: errorText }, true);
      sendBtn.disabled = false;
      activeStream = null;
    },
  });
}

function createNewChat() {
  const id = `chat_${Date.now()}`;
  
  // Always start with welcome message only for new chats
  chatHistory[id] = {
    title: 'New Chat',
    messages: [{ sender: 'bot', text: 'Hello! I am ready to answer questions about your documents.' }]
  };
  
  activeChatId = id;
  localStorage.setItem('activeChatId', id);
  updateAndRenderHistory();
  loadChat(id);
  return id;
}

function loadChat(id) {
  if (!chatHistory[id]) {
    console.warn(`Chat with id ${id} not found. Starting a new one.`);
    activeChatId = createNewChat();
    return;
  }
  
  // Get fresh copy from localStorage to ensure we have latest data
  const savedHistory = JSON.parse(localStorage.getItem('chatHistory')) || {};
  const chat = savedHistory[id] || chatHistory[id];
  
  if (!chat.messages || !Array.isArray(chat.messages)) {
    chat.messages = [];
  }
  
  activeChatId = id;
  localStorage.setItem('activeChatId', id);
  chatHistory[id] = chat; // Update in-memory chat with latest data
  
  const chatWindow = document.getElementById('chat-window');
  chatWindow.innerHTML = '';
  
  // Render all messages in order
  chat.messages.forEach(msg => {
    if (msg && msg.text && (msg.sender === 'user' || msg.sender === 'bot')) {
      appendMessage(msg);
    }
  });
  
  renderHistoryList();
  document.querySelector('.crumb').textContent = chat.title;
  scrollToBottom();
}

function renderHistoryList() {
  const historyList = document.getElementById('history-list');
  if (!historyList) return;
  historyList.innerHTML = '';
  Object.keys(chatHistory).sort((a, b) => b.split('_')[1] - a.split('_')[1]).forEach(id => {
    const chat = chatHistory[id];
    const li = document.createElement('li');
    li.className = 'chat-item';
    li.dataset.chatId = id;
    if (id === activeChatId) li.classList.add('active');
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'chat-item-title';
    titleSpan.textContent = chat.title;
    
    const menuBtn = document.createElement('button');
    menuBtn.className = 'chat-item-menu-btn';
    menuBtn.innerHTML = '<i class="fas fa-ellipsis-h"></i>';
    menuBtn.title = 'Chat Options';

    menuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      
      const existingMenu = document.querySelector('.menu-panel');
      if (existingMenu) {
        existingMenu.remove();
      }

      const menuPanel = document.createElement('div');
      menuPanel.className = 'menu-panel';
      menuPanel.innerHTML = `
        <button class="menu-item" data-action="rename"><i class="fas fa-pencil-alt"></i> Rename</button>
        <button class="menu-item" data-action="share"><i class="fas fa-share-alt"></i> Share</button>
        <button class="menu-item danger" data-action="delete"><i class="fas fa-trash-can"></i> Delete</button>
      `;
      
      document.body.appendChild(menuPanel);

      const rect = menuBtn.getBoundingClientRect();
      menuPanel.style.top = `${rect.bottom}px`;
      menuPanel.style.left = `${rect.left}px`;
      menuPanel.classList.add('show');

      menuPanel.addEventListener('click', (e) => {
          e.stopPropagation();
          const target = e.target.closest('.menu-item');
          if (!target) return;

          const action = target.dataset.action;
          if (action === 'delete') {
              if (confirm(`Are you sure you want to delete "${chat.title}"?`)) {
                  delete chatHistory[id];
                  if (id === activeChatId) {
                      const remainingIds = Object.keys(chatHistory).sort((a, b) => b.split('_')[1] - a.split('_')[1]);
                      activeChatId = remainingIds.length > 0 ? remainingIds[0] : createNewChat();
                      loadChat(activeChatId);
                  }
                  updateAndRenderHistory();
              }
          } else if (action === 'rename') {
              const newTitle = prompt('Enter new chat title:', chat.title);
              if (newTitle) {
                  chatHistory[id].title = newTitle;
                  updateAndRenderHistory();
              }
          } else if (action === 'share') {
              showShareModal(id);
          }
          menuPanel.remove();
      });
    });

    li.appendChild(titleSpan);
    li.appendChild(menuBtn);

    li.addEventListener('click', () => {
      if (activeStream) activeStream.close();
      loadChat(id);
    });
    historyList.appendChild(li);
  });
}

function showShareModal(chatId) {
  const modal = document.getElementById('share-modal');
  const closeModalBtn = document.getElementById('close-modal-btn');
  const shareLinkInput = document.getElementById('share-link-input');
  const copyLinkBtn = document.getElementById('copy-link-btn');
  const copyChatBtn = document.getElementById('copy-chat-btn');

  const shareUrl = `${window.location.origin}${window.location.pathname}?chat=${chatId}`;
  shareLinkInput.value = shareUrl;

  modal.style.display = 'flex';

  closeModalBtn.onclick = () => {
    modal.style.display = 'none';
  };

  copyLinkBtn.onclick = () => {
    copyToClipboard(shareLinkInput.value, copyLinkBtn, '<i class="fas fa-copy"></i> Copy Link');
  };

  copyChatBtn.onclick = () => {
    const chat = chatHistory[chatId];
    if (!chat) return;

    const chatText = chat.messages.map(msg => {
      return `[${msg.sender.toUpperCase()}]\n${msg.text}`;
    }).join('\n\n');
    
    copyToClipboard(chatText, copyChatBtn, '<i class="fas fa-paste"></i> Copy Chat to Clipboard');
  };

  window.onclick = (event) => {
    if (event.target == modal) {
      modal.style.display = 'none';
    }
  };
}

function copyToClipboard(text, btn, originalContent) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => {
      btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
      setTimeout(() => {
        btn.innerHTML = originalContent;
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy text: ', err);
      btn.innerHTML = '<i class="fas fa-times"></i> Failed';
      setTimeout(() => {
        btn.innerHTML = originalContent;
      }, 2000);
    });
  } else {
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'absolute';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      const successful = document.execCommand('copy');
      if (successful) {
        btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
      } else {
        btn.innerHTML = '<i class="fas fa-times"></i> Failed';
      }
    } catch (err) {
      console.error('Fallback copy failed: ', err);
      btn.innerHTML = '<i class="fas fa-times"></i> Failed';
    }
    document.body.removeChild(textArea);
    setTimeout(() => {
      btn.innerHTML = originalContent;
    }, 2000);
  }
}

function updateAndRenderHistory() {
  // First ensure we have the latest history from localStorage
  const savedHistory = JSON.parse(localStorage.getItem('chatHistory')) || {};
  
  // Update only the active chat in the saved history
  if (activeChatId && chatHistory[activeChatId]) {
    savedHistory[activeChatId] = chatHistory[activeChatId];
  }
  
  // Save back to localStorage
  localStorage.setItem('chatHistory', JSON.stringify(savedHistory));
  localStorage.setItem('activeChatId', activeChatId);
  
  // Update our in-memory history
  chatHistory = savedHistory;
  
  renderHistoryList();
}

function addMessageToHistory(message, overwriteLast = false) {
  const chat = chatHistory[activeChatId];
  if (!chat) return;

  // Get the latest version of this chat from localStorage
  const savedHistory = JSON.parse(localStorage.getItem('chatHistory')) || {};
  const savedChat = savedHistory[activeChatId] || chat;

  // Ensure messages array exists
  if (!savedChat.messages) {
    savedChat.messages = [];
  }

  // Update messages
  if (overwriteLast && savedChat.messages.length > 0) {
    savedChat.messages[savedChat.messages.length - 1] = message;
  } else {
    savedChat.messages.push(message);
  }

  // Update both in-memory and localStorage versions
  chatHistory[activeChatId] = savedChat;
  savedHistory[activeChatId] = savedChat;
  
  // Immediately save to localStorage to prevent losing messages
  localStorage.setItem('chatHistory', JSON.stringify(savedHistory));
  
  if (chat.title === 'New Chat' && message.sender === 'user') {
    console.log('Generating title for:', message.text);
    getChatTitle(message.text, activeChatId)
      .then(({ title, chatId }) => {
        console.log('Received title:', title);
        if (chatHistory[chatId]) {
          chatHistory[chatId].title = title;
          savedHistory[chatId].title = title;
          document.querySelector('.crumb').textContent = title;
          const chatItem = document.querySelector(`.chat-item[data-chat-id="${chatId}"] .chat-item-title`);
          if (chatItem) {
            chatItem.textContent = title;
          }
          localStorage.setItem('chatHistory', JSON.stringify(savedHistory));
          renderHistoryList();
        }
      })
      .catch(error => {
        console.error('Failed to get chat title:', error);
        renderHistoryList();
      });
  } else {
    renderHistoryList();
  }
}

function appendMessage(message) {
  const chatWindow = document.getElementById('chat-window');
  const msgWrapper = document.createElement('div');
  msgWrapper.className = `message ${message.sender}-message`;
  
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.innerHTML = message.sender === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  
  if (message.sender === 'bot') {
    renderBotMessage(contentDiv, { 
      text: message.text || '', 
      sources: message.sources || [] 
    });
  } else if (message.sender === 'user' && message.text) {
    const p = document.createElement('p');
    p.textContent = message.text;
    contentDiv.appendChild(p);
  }
  
  msgWrapper.appendChild(avatar);
  msgWrapper.appendChild(contentDiv);
  chatWindow.appendChild(msgWrapper);
  scrollToBottom();
  
  return contentDiv;
}

function scrollToBottom() {
  const chatWindow = document.getElementById('chat-window');
  chatWindow.scrollTop = chatWindow.scrollHeight;
}