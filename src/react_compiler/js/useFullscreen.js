import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook for fullscreen functionality
 * 
 * @returns {Object} Object containing:
 *   - isFullscreen: boolean indicating if currently in fullscreen
 *   - toggleFullscreen: function to toggle fullscreen mode
 *   - containerRef: ref to attach to the element that should go fullscreen
 * 
 * @example
 * const MyWidget = () => {
 *   const { isFullscreen, toggleFullscreen, containerRef } = useFullscreen();
 *   
 *   return (
 *     <div ref={containerRef} className={isFullscreen ? 'w-fullscreen' : 'w-container'}>
 *       <button onClick={toggleFullscreen}>
 *         {isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
 *       </button>
 *     </div>
 *   );
 * };
 */
export const useFullscreen = () => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef(null);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        // Enter fullscreen mode
        const element = containerRef.current || document.documentElement;
        if (element.requestFullscreen) {
          await element.requestFullscreen();
        } else if (element.mozRequestFullScreen) {
          await element.mozRequestFullScreen();
        } else if (element.webkitRequestFullscreen) {
          await element.webkitRequestFullscreen();
        } else if (element.msRequestFullscreen) {
          await element.msRequestFullscreen();
        }
      } else {
        // Exit fullscreen mode
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if (document.mozCancelFullScreen) {
          await document.mozCancelFullScreen();
        } else if (document.webkitExitFullscreen) {
          await document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
          await document.msExitFullscreen();
        }
      }
    } catch (error) {
      console.error('Fullscreen toggle failed:', error);
    }
  };

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('msfullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('msfullscreenchange', handleFullscreenChange);
    };
  }, []);

  return {
    isFullscreen,
    toggleFullscreen,
    containerRef
  };
};

export default useFullscreen;