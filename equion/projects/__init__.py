"""프로젝트 — 부품(블록 파일의 식)과 조립(equion.toml) 층 (D32), 자료 정의와 자료 회차 (D34). 여는 법: `eqn.project(폴더)`."""
from .assembly import AssemblyReport
from .config import FORMAT, FORMAT_VERSION, ProjectConfig, ProjectError, load_config
from .identity import IdentityCheck
from .parts import Part
from .project import ImpactReport, Project, open_project
from .vintage import AddResult, BuildResult, VintageDiff

__all__ = ["Project", "open_project", "ProjectError", "AssemblyReport", "IdentityCheck", "Part",
           "BuildResult", "VintageDiff", "ImpactReport", "AddResult",
           "ProjectConfig", "load_config", "FORMAT", "FORMAT_VERSION"]
