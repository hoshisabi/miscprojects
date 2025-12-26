import pygame
import os

# --- 1. INITIALIZATION ---
pygame.init()

# Define constants
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 500  # Extra space for the buttons
PIPE_SIZE = 100
GRID_START_X = 100
GRID_START_Y = 50
BUTTON_HEIGHT = 40

SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Pipe Rotation Puzzle")

# --- 2. ASSET LOADING ---
# Load 4 pipe images. Make sure these files are in the same directory!
pipe_images = []
try:
    for i in range(1, 5):
        # NOTE: pipeGrey_01 is assumed to be index 0, pipeGrey_04 is index 3
        img = pygame.image.load(os.path.join('pipeGrey_0' + str(i) + '.png')).convert_alpha()
        pipe_images.append(pygame.transform.scale(img, (PIPE_SIZE, PIPE_SIZE)))
except pygame.error as e:
    print(f"Error loading images. Ensure 'pipeGrey_01.png' through 'pipeGrey_04.png' exist: {e}")
    pygame.quit()
    exit()

# --- 3. GAME STATE ---
# (UL, UL, DR, DR) -> (3, 3, 1, 1) using the indices defined above
# 0:UR, 1:DR, 2:DL, 3:UL
SCRAMBLED_STATE = [3, 3, 1, 1]
GOAL_STATE = [1, 2, 0, 3] # (DR, DL, UR, UL)

# The current state of the 4 pipes (index of the image to display)
pipes = list(SCRAMBLED_STATE)

# --- 4. GAME FUNCTIONS ---

def rotate_pipe(pipe_index):
    """Rotates a pipe 90 degrees clockwise (advances the index)"""
    pipes[pipe_index] = (pipes[pipe_index] + 1) % 4

def check_win():
    """Checks if the current pipe configuration matches the goal state"""
    return pipes == GOAL_STATE

def draw_pipes():
    """Draws the 4 pipes based on the current 'pipes' state"""
    # TL (0)
    SCREEN.blit(pipe_images[pipes[0]], (GRID_START_X, GRID_START_Y))
    # TR (1)
    SCREEN.blit(pipe_images[pipes[1]], (GRID_START_X + PIPE_SIZE, GRID_START_Y))
    # BL (2)
    SCREEN.blit(pipe_images[pipes[2]], (GRID_START_X, GRID_START_Y + PIPE_SIZE))
    # BR (3)
    SCREEN.blit(pipe_images[pipes[3]], (GRID_START_X + PIPE_SIZE, GRID_START_Y + PIPE_SIZE))

# Basic Button class for handling UI
class Button:
    def __init__(self, x, y, width, height, text, action):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.font = pygame.font.Font(None, 24)
        
    def draw(self):
        pygame.draw.rect(SCREEN, (180, 180, 180), self.rect)
        text_surface = self.font.render(self.text, True, (0, 0, 0))
        text_rect = text_surface.get_rect(center=self.rect.center)
        SCREEN.blit(text_surface, text_rect)
        
    def handle_click(self, pos):
        if self.rect.collidepoint(pos):
            self.action()
            return True
        return False

# Define button actions
def top_rotate():
    rotate_pipe(0) # TL
    rotate_pipe(1) # TR
def bottom_rotate():
    rotate_pipe(2) # BL
    rotate_pipe(3) # BR
def left_rotate():
    rotate_pipe(0) # TL
    rotate_pipe(2) # BL
def right_rotate():
    rotate_pipe(1) # TR
    rotate_pipe(3) # BR
    
# Create buttons
buttons = [
    Button(5, GRID_START_Y + 70, 80, 40, "LEFT", left_rotate),
    Button(SCREEN_WIDTH - 85, GRID_START_Y + 70, 80, 40, "RIGHT", right_rotate),
    Button(GRID_START_X + 60, GRID_START_Y - 45, 80, 40, "TOP", top_rotate),
    Button(GRID_START_X + 60, GRID_START_Y + 2*PIPE_SIZE + 5, 80, 40, "BOTTOM", bottom_rotate)
]

# --- 5. GAME LOOP ---
running = True
win_status = False
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN and not win_status:
            for button in buttons:
                if button.handle_click(event.pos):
                    # Check win condition after every successful move
                    win_status = check_win()
                    break

    # Drawing
    SCREEN.fill((255, 255, 255)) # White background
    
    draw_pipes()
    
    for button in buttons:
        button.draw()

    if win_status:
        # Display Win Message
        font = pygame.font.Font(None, 74)
        text = font.render("SOLVED!", True, (0, 150, 0))
        SCREEN.blit(text, text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT - 50)))

    pygame.display.flip()

pygame.quit()
