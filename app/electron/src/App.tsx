import React from 'react';
import { HashRouter, Route, Routes } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import OverlayPage from './pages/Overlay';
import SettingsPage from './pages/Settings';

const App: React.FC = () => (
  <AppProvider>
    <HashRouter>
      <Routes>
        <Route path="/" element={<OverlayPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </HashRouter>
  </AppProvider>
);

export default App;
