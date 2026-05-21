import sys
from pathlib import Path

import pygame

SCREEN_WIDTH = 400
SCREEN_HEIGHT = 500
PIPE_SIZE = 100
GRID_START_X = 100
GRID_START_Y = 50

SCRAMBLED_STATE = [3, 3, 1, 1]
GOAL_STATE = [1, 2, 0, 3]


def asset_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent / "assets"


def load_pipe_images() -> list[pygame.Surface]:
    images = []
    for i in range(1, 5):
        path = asset_dir() / f"pipeGrey_0{i}.png"
        img = pygame.image.load(path).convert_alpha()
        images.append(pygame.transform.scale(img, (PIPE_SIZE, PIPE_SIZE)))
    return images


def rotate_pipe(pipes: list[int], pipe_index: int) -> None:
    pipes[pipe_index] = (pipes[pipe_index] + 1) % 4


def check_win(pipes: list[int]) -> bool:
    return pipes == GOAL_STATE


def draw_pipes(screen: pygame.Surface, pipe_images: list[pygame.Surface], pipes: list[int]) -> None:
    screen.blit(pipe_images[pipes[0]], (GRID_START_X, GRID_START_Y))
    screen.blit(pipe_images[pipes[1]], (GRID_START_X + PIPE_SIZE, GRID_START_Y))
    screen.blit(pipe_images[pipes[2]], (GRID_START_X, GRID_START_Y + PIPE_SIZE))
    screen.blit(pipe_images[pipes[3]], (GRID_START_X + PIPE_SIZE, GRID_START_Y + PIPE_SIZE))


class Button:
    def __init__(self, screen: pygame.Surface, x: int, y: int, width: int, height: int, text: str, action):
        self.screen = screen
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.font = pygame.font.Font(None, 24)

    def draw(self) -> None:
        pygame.draw.rect(self.screen, (180, 180, 180), self.rect)
        text_surface = self.font.render(self.text, True, (0, 0, 0))
        self.screen.blit(text_surface, text_surface.get_rect(center=self.rect.center))

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self.rect.collidepoint(pos):
            self.action()
            return True
        return False


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pipe Rotation Puzzle")

    try:
        pipe_images = load_pipe_images()
    except pygame.error as e:
        print(f"Error loading images from {asset_dir()}: {e}")
        pygame.quit()
        sys.exit(1)

    pipes = list(SCRAMBLED_STATE)

    def top_rotate():
        rotate_pipe(pipes, 0)
        rotate_pipe(pipes, 1)

    def bottom_rotate():
        rotate_pipe(pipes, 2)
        rotate_pipe(pipes, 3)

    def left_rotate():
        rotate_pipe(pipes, 0)
        rotate_pipe(pipes, 2)

    def right_rotate():
        rotate_pipe(pipes, 1)
        rotate_pipe(pipes, 3)

    buttons = [
        Button(screen, 5, GRID_START_Y + 70, 80, 40, "LEFT", left_rotate),
        Button(screen, SCREEN_WIDTH - 85, GRID_START_Y + 70, 80, 40, "RIGHT", right_rotate),
        Button(screen, GRID_START_X + 60, GRID_START_Y - 45, 80, 40, "TOP", top_rotate),
        Button(screen, GRID_START_X + 60, GRID_START_Y + 2 * PIPE_SIZE + 5, 80, 40, "BOTTOM", bottom_rotate),
    ]

    running = True
    win_status = False
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and not win_status:
                for button in buttons:
                    if button.handle_click(event.pos):
                        win_status = check_win(pipes)
                        break

        screen.fill((255, 255, 255))
        draw_pipes(screen, pipe_images, pipes)
        for button in buttons:
            button.draw()

        if win_status:
            font = pygame.font.Font(None, 74)
            text = font.render("SOLVED!", True, (0, 150, 0))
            screen.blit(text, text.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT - 50)))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
